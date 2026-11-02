// Proxy Atlas Checker validates proxies without loading the input into memory.
package main

import (
	"bufio"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

type config struct {
	workers        int
	timeout        time.Duration
	connectTimeout time.Duration
	testURL        string
}

type result struct {
	Proxy     string `json:"proxy"`
	Valid     bool   `json:"valid"`
	LatencyMS int64  `json:"latency_ms"`
	Error     string `json:"error,omitempty"`
}

func normalize(raw string) (*url.URL, error) {
	if !strings.Contains(raw, "://") {
		raw = "http://" + raw
	}
	u, err := url.Parse(raw)
	if err != nil {
		return nil, err
	}
	u.Scheme = strings.ToLower(u.Scheme)
	switch u.Scheme {
	case "http", "https", "socks4", "socks4a", "socks5", "socks5h":
	default:
		return nil, errors.New("unsupported protocol")
	}
	if u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" {
		return nil, errors.New("expected scheme://IP:port without credentials or path")
	}
	ip := net.ParseIP(u.Hostname())
	port, err := strconv.Atoi(u.Port())
	if ip == nil || err != nil || port < 1 || port > 65535 {
		return nil, errors.New("invalid IP or port")
	}
	u.Host = net.JoinHostPort(ip.String(), strconv.Itoa(port))
	return u, nil
}

// socksDial supports local DNS (4/5) and proxy DNS (4a/5h), with one deadline
// covering the connect and handshake. The HTTP request has its own context.
func socksDial(proxy *url.URL, timeout time.Duration) func(context.Context, string, string) (net.Conn, error) {
	return func(ctx context.Context, network, address string) (net.Conn, error) {
		ctx, cancel := context.WithTimeout(ctx, timeout)
		defer cancel()
		conn, err := (&net.Dialer{}).DialContext(ctx, "tcp", proxy.Host)
		if err != nil {
			return nil, err
		}
		ok := false
		defer func() {
			if !ok {
				conn.Close()
			}
		}()
		deadline, _ := ctx.Deadline()
		conn.SetDeadline(deadline)
		stop := context.AfterFunc(ctx, func() { conn.Close() })
		defer stop()
		host, portText, err := net.SplitHostPort(address)
		if err != nil {
			return nil, err
		}
		port, err := strconv.Atoi(portText)
		if err != nil || port < 1 || port > 65535 {
			return nil, errors.New("invalid target port")
		}
		ip := net.ParseIP(host)
		localDNS := proxy.Scheme == "socks4" || proxy.Scheme == "socks5"
		if ip == nil && localDNS {
			ips, err := net.DefaultResolver.LookupIP(ctx, "ip", host)
			if err != nil {
				return nil, err
			}
			for _, candidate := range ips {
				if proxy.Scheme == "socks5" || candidate.To4() != nil {
					ip = candidate
					break
				}
			}
			if ip == nil {
				return nil, errors.New("no compatible target IP")
			}
		}
		if strings.HasPrefix(proxy.Scheme, "socks4") {
			packet := []byte{4, 1, byte(port >> 8), byte(port), 0, 0, 0, 1, 0}
			if ip != nil {
				v4 := ip.To4()
				if v4 == nil {
					return nil, errors.New("SOCKS4 requires an IPv4 target")
				}
				copy(packet[4:8], v4)
			} else {
				packet = append(packet, []byte(host)...)
				packet = append(packet, 0)
			}
			if _, err = conn.Write(packet); err != nil {
				return nil, err
			}
			var reply [8]byte
			if _, err = io.ReadFull(conn, reply[:]); err != nil {
				return nil, err
			}
			if reply[0] != 0 || reply[1] != 90 {
				return nil, errors.New("SOCKS4 connection rejected")
			}
		} else {
			if _, err = conn.Write([]byte{5, 1, 0}); err != nil {
				return nil, err
			}
			var greeting [2]byte
			if _, err = io.ReadFull(conn, greeting[:]); err != nil {
				return nil, err
			}
			if greeting != [2]byte{5, 0} {
				return nil, errors.New("SOCKS5 requires unsupported authentication")
			}
			packet := []byte{5, 1, 0}
			if v4 := ip.To4(); v4 != nil {
				packet = append(packet, 1)
				packet = append(packet, v4...)
			} else if ip != nil {
				packet = append(packet, 4)
				packet = append(packet, ip.To16()...)
			} else {
				if len(host) > 255 {
					return nil, errors.New("target hostname too long")
				}
				packet = append(packet, 3, byte(len(host)))
				packet = append(packet, []byte(host)...)
			}
			packet = binary.BigEndian.AppendUint16(packet, uint16(port))
			if _, err = conn.Write(packet); err != nil {
				return nil, err
			}
			var reply [4]byte
			if _, err = io.ReadFull(conn, reply[:]); err != nil {
				return nil, err
			}
			if reply[0] != 5 || reply[1] != 0 || reply[2] != 0 {
				return nil, errors.New("SOCKS5 connection rejected")
			}
			length := 0
			switch reply[3] {
			case 1:
				length = 4
			case 4:
				length = 16
			case 3:
				var size [1]byte
				if _, err = io.ReadFull(conn, size[:]); err != nil {
					return nil, err
				}
				length = int(size[0])
			default:
				return nil, errors.New("invalid SOCKS5 reply")
			}
			if _, err = io.CopyN(io.Discard, conn, int64(length+2)); err != nil {
				return nil, err
			}
		}
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		if !stop() {
			return nil, context.Canceled
		}
		conn.SetDeadline(time.Time{})
		ok = true
		return conn, nil
	}
}

func validate(ctx context.Context, raw string, cfg config) result {
	started := time.Now()
	r := result{Proxy: raw}
	err := check(ctx, raw, cfg)
	r.LatencyMS = time.Since(started).Milliseconds()
	r.Valid = err == nil
	if err != nil {
		r.Error = err.Error()
	}
	return r
}

func check(ctx context.Context, raw string, cfg config) error {
	proxy, err := normalize(raw)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(ctx, cfg.timeout)
	defer cancel()
	transport := &http.Transport{
		Proxy:                  http.ProxyURL(proxy),
		DialContext:            (&net.Dialer{Timeout: cfg.connectTimeout}).DialContext,
		TLSHandshakeTimeout:    cfg.connectTimeout,
		DisableKeepAlives:      true,
		MaxResponseHeaderBytes: 16384,
	}
	if strings.HasPrefix(proxy.Scheme, "socks") {
		transport.Proxy = nil
		transport.DialContext = socksDial(proxy, cfg.connectTimeout)
	}
	defer transport.CloseIdleConnections()
	client := http.Client{Transport: transport, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	req, err := http.NewRequestWithContext(ctx, "GET", cfg.testURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "ProxyAtlas-Checker/1.0")
	response, err := client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("HTTP status %d", response.StatusCode)
	}
	payload, err := io.ReadAll(io.LimitReader(response.Body, 65537))
	if err != nil {
		return err
	}
	if len(payload) > 65536 {
		return errors.New("response exceeds 64 KiB")
	}
	var data map[string]json.RawMessage
	if err = json.Unmarshal(payload, &data); err != nil {
		return err
	}
	value, found := data["origin"]
	if !found {
		value = data["ip"]
	}
	var origin string
	if err = json.Unmarshal(value, &origin); err != nil {
		return errors.New("missing or invalid origin/ip")
	}
	for _, ip := range strings.Split(origin, ",") {
		if net.ParseIP(strings.TrimSpace(ip)) == nil {
			return errors.New("origin/ip is not an IP address")
		}
	}
	return nil
}

func run(ctx context.Context, input io.Reader, output io.Writer, cfg config, format string) error {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	jobs := make(chan string, cfg.workers)
	results := make(chan result, cfg.workers)
	readErr := make(chan error, 1)
	go func() {
		defer close(jobs)
		scanner := bufio.NewScanner(input)
		scanner.Buffer(make([]byte, 4096), 65536)
		for scanner.Scan() {
			line := strings.TrimSpace(strings.TrimPrefix(scanner.Text(), "\ufeff"))
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			select {
			case jobs <- line:
			case <-ctx.Done():
				readErr <- ctx.Err()
				return
			}
		}
		readErr <- scanner.Err()
	}()
	var workers sync.WaitGroup
	for i := 0; i < cfg.workers; i++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			for {
				var raw string
				select {
				case <-ctx.Done():
					return
				case value, ok := <-jobs:
					if !ok {
						return
					}
					raw = value
				}
				r := validate(ctx, raw, cfg)
				select {
				case results <- r:
				case <-ctx.Done():
					return
				}
			}
		}()
	}
	go func() { workers.Wait(); close(results) }()
	encoder := json.NewEncoder(output)
	for r := range results {
		var err error
		if format == "jsonl" {
			err = encoder.Encode(r)
		} else if r.Valid {
			u, _ := normalize(r.Proxy)
			_, err = fmt.Fprintln(output, u.String())
		}
		if err != nil {
			cancel()
			workers.Wait()
			return err
		}
	}
	if ctx.Err() != nil {
		return ctx.Err()
	}
	return <-readErr
}

func main() {
	inputPath := flag.String("input", "-", "Input list, one proxy per line; - for stdin")
	outputPath := flag.String("output", "-", "Output file; - for stdout")
	format := flag.String("format", "jsonl", "jsonl (all checks) or txt (valid proxies)")
	workers := flag.Int("workers", 128, "Concurrent checks (1-4096)")
	timeout := flag.Duration("timeout", 5*time.Second, "Total deadline per check")
	connectTimeout := flag.Duration("connect-timeout", 2*time.Second, "Connection and SOCKS handshake deadline")
	testURL := flag.String("test-url", "https://httpbin.org/ip", "JSON IP endpoint")
	flag.Parse()
	fail := func(err error) { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
	if *workers < 1 || *workers > 4096 || *timeout <= 0 || *connectTimeout <= 0 {
		fail(errors.New("invalid workers or timeout"))
	}
	if *format != "txt" && *format != "jsonl" {
		fail(errors.New("format must be txt or jsonl"))
	}
	u, err := url.Parse(*testURL)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") {
		fail(errors.New("test-url must be HTTP(S)"))
	}
	input := os.Stdin
	if *inputPath != "-" {
		input, err = os.Open(*inputPath)
		if err != nil {
			fail(err)
		}
		defer input.Close()
	}
	output := os.Stdout
	if *outputPath != "-" {
		output, err = os.CreateTemp(filepath.Dir(*outputPath), ".proxy-atlas-checks-*.tmp")
		if err != nil {
			fail(err)
		}
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	buffer := bufio.NewWriterSize(output, 65536)
	err = run(ctx, input, buffer, config{*workers, *timeout, *connectTimeout, *testURL}, *format)
	if flushErr := buffer.Flush(); err == nil {
		err = flushErr
	}
	if *outputPath != "-" {
		name := output.Name()
		if closeErr := output.Close(); err == nil {
			err = closeErr
		}
		if err == nil {
			err = os.Rename(name, *outputPath)
		}
		if err != nil {
			os.Remove(name)
		}
	}
	if err != nil {
		fail(err)
	}
}
