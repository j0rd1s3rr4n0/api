# Histórico persistente

`pool.sqlite3` y `pool.csv` son los archivos de trabajo locales de Proxy Atlas. Se conservan en disco y están excluidos de Git por su tamaño.

`pool.csv.gz` es una copia comprimida del CSV histórico incluida en el repositorio. Conserva las fechas y los estados del momento en que se creó; no se actualiza automáticamente en cada ejecución. Puede abrirse con una herramienta compatible con gzip o descomprimirse para consultar sus datos.

Proxy Atlas utiliza SQLite, no el archivo gzip, durante sus ejecuciones. En un clon nuevo el snapshot no se importa automáticamente al pool.
