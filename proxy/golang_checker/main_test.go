package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func testConfig(endpoint string) config {
	return config{workers: 4, timeout: time.Second, connectTimeout: time.Second, testURL: endpoint}
}

func TestHTTPResponses(t *testing.T) {
	for _, tc := range []struct {
		name, body string
		status     int
		valid      bool
	}{
		{"origin", `{"origin":"203.0.113.1, ::1"}`, 200, true},
		{"ip", `{"ip":"203.0.113.1"}`, 200, true},
		{"html", `<html>Login</html>`, 200, false},
		{"redirect", `{"ip":"203.0.113.1"}`, 302, false},
		{"invalid", `{"origin":"no-ip"}`, 200, false},
		{"empty", `{"origin":""}`, 200, false},
		{"missing", `{}`, 200, false},
		{"type", `{"origin":123}`, 200, false},
		{"null", `null`, 200, false},
		{"large", strings.Repeat(" ", 65537), 200, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if !r.URL.IsAbs() {
					t.Error("HTTP request did not use proxy form")
				}
				w.WriteHeader(tc.status)
				io.WriteString(w, tc.body)
			}))
			defer server.Close()
			got := validate(context.Background(), server.URL, testConfig("http://unresolvable.invalid/ip"))
			if got.Valid != tc.valid {
				t.Fatalf("got %+v, wanted valid=%v", got, tc.valid)
			}
		})
	}
}

func TestTLSCertificatesVerified(t *testing.T) {
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, `{"ip":"203.0.113.1"}`)
	}))
	defer server.Close()
	if validate(context.Background(), server.URL, testConfig("http://test.invalid/ip")).Valid {
		t.Fatal("accepted an untrusted TLS proxy")
	}
}

func TestHTTPSUsesCONNECT(t *testing.T) {
	var connected atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "CONNECT" && r.Host == "test.invalid:443" {
			connected.Store(true)
		}
		w.WriteHeader(http.StatusForbidden)
	}))
	defer server.Close()
	if validate(context.Background(), server.URL, testConfig("https://test.invalid/ip")).Valid {
		t.Fatal("accepted rejected CONNECT")
	}
	if !connected.Load() {
		t.Fatal("HTTPS did not request a CONNECT tunnel")
	}
}

func TestDeadline(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { <-r.Context().Done() }))
	defer server.Close()
	cfg := testConfig("http://test.invalid/ip")
	cfg.timeout = 30 * time.Millisecond
	start := time.Now()
	if validate(context.Background(), server.URL, cfg).Valid {
		t.Fatal("accepted stalled proxy")
	}
	if time.Since(start) > time.Second {
		t.Fatal("deadline was not enforced")
	}
}

func TestSOCKSProtocols(t *testing.T) {
	for _, scheme := range []string{"socks4", "socks4a", "socks5", "socks5h"} {
		t.Run(scheme, func(t *testing.T) {
			listener, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatal(err)
			}
			defer listener.Close()
			done := make(chan error, 1)
			go func() {
				conn, err := listener.Accept()
				if err != nil {
					done <- err
					return
				}
				defer conn.Close()
				conn.SetDeadline(time.Now().Add(2 * time.Second))
				reader := bufio.NewReader(conn)
				if strings.HasPrefix(scheme, "socks4") {
					header := make([]byte, 8)
					if _, err := io.ReadFull(reader, header); err != nil {
						done <- err
						return
					}
					if header[0] != 4 || header[1] != 1 {
						done <- fmt.Errorf("invalid SOCKS4 header")
						return
					}
					if _, err := reader.ReadString(0); err != nil {
						done <- err
						return
					}
					if scheme == "socks4a" {
						host, err := reader.ReadString(0)
						if err != nil || host != "remote.invalid\x00" {
							done <- fmt.Errorf("SOCKS4a did not forward hostname: %q", host)
							return
						}
					}
					conn.Write([]byte{0, 90, 0, 0, 0, 0, 0, 0})
				} else {
					greeting := make([]byte, 3)
					if _, err := io.ReadFull(reader, greeting); err != nil {
						done <- err
						return
					}
					if !bytes.Equal(greeting, []byte{5, 1, 0}) {
						done <- fmt.Errorf("invalid SOCKS5 greeting")
						return
					}
					conn.Write([]byte{5, 0})
					header := make([]byte, 4)
					if _, err := io.ReadFull(reader, header); err != nil {
						done <- err
						return
					}
					if scheme == "socks5h" {
						if header[3] != 3 {
							done <- fmt.Errorf("expected remote DNS")
							return
						}
						size, err := reader.ReadByte()
						if err != nil {
							done <- err
							return
						}
						host := make([]byte, int(size))
						if _, err := io.ReadFull(reader, host); err != nil {
							done <- err
							return
						}
						if string(host) != "remote.invalid" {
							done <- fmt.Errorf("wrong remote hostname")
							return
						}
					} else {
						if header[3] != 1 {
							done <- fmt.Errorf("expected IPv4")
							return
						}
						if _, err := io.CopyN(io.Discard, reader, 4); err != nil {
							done <- err
							return
						}
					}
					if _, err := io.CopyN(io.Discard, reader, 2); err != nil {
						done <- err
						return
					}
					conn.Write([]byte{5, 0, 0, 1, 0, 0, 0, 0, 0, 0})
				}
				request, err := http.ReadRequest(reader)
				if err != nil {
					done <- err
					return
				}
				request.Body.Close()
				body := `{"origin":"203.0.113.1"}`
				_, err = fmt.Fprintf(conn, "HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s", len(body), body)
				done <- err
			}()
			target := "http://127.0.0.1/ip"
			if scheme == "socks4a" || scheme == "socks5h" {
				target = "http://remote.invalid/ip"
			}
			result := validate(context.Background(), scheme+"://"+listener.Addr().String(), testConfig(target))
			if err := <-done; err != nil {
				t.Fatal(err)
			}
			if !result.Valid {
				t.Fatalf("SOCKS validation failed: %+v", result)
			}
		})
	}
}

func TestStreamingWorkerLimit(t *testing.T) {
	var active, peak atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count := active.Add(1)
		defer active.Add(-1)
		for old := peak.Load(); count > old; old = peak.Load() {
			if peak.CompareAndSwap(old, count) {
				break
			}
		}
		time.Sleep(time.Millisecond)
		io.WriteString(w, `{"ip":"203.0.113.1"}`)
	}))
	defer server.Close()
	input := strings.NewReader("# comment\n\n" + strings.Repeat(server.URL+"\n", 50))
	var out bytes.Buffer
	cfg := testConfig("http://test.invalid/ip")
	if err := run(context.Background(), input, &out, cfg, "jsonl"); err != nil {
		t.Fatal(err)
	}
	scanner := bufio.NewScanner(&out)
	count := 0
	for scanner.Scan() {
		var r result
		if err := json.Unmarshal(scanner.Bytes(), &r); err != nil || !r.Valid {
			t.Fatalf("bad result %s", scanner.Text())
		}
		count++
	}
	if count != 50 || peak.Load() > int32(cfg.workers) {
		t.Fatalf("count=%d peak=%d", count, peak.Load())
	}
}

func TestInvalidInput(t *testing.T) {
	for _, raw := range []string{"quic://1.2.3.4:80", "1.2.3.4:99999", "999.2.3.4:80", "http://user:pass@1.2.3.4:80", "http://1.2.3.4:80/path"} {
		if _, err := normalize(raw); err == nil {
			t.Errorf("accepted %q", raw)
		}
	}
}

func TestCancellationWithIdleInput(t *testing.T) {
	input, writer := io.Pipe()
	defer input.Close()
	defer writer.Close()
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- run(ctx, input, io.Discard, testConfig("http://test.invalid/ip"), "jsonl") }()
	cancel()
	select {
	case err := <-done:
		if err == nil {
			t.Fatal("expected cancellation")
		}
	case <-time.After(time.Second):
		t.Fatal("workers did not stop with idle input")
	}
}
