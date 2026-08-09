import sqlite3
from datetime import datetime, timezone


NOMBRE_BASE_DATOS = "monitor.db"

SERVICIOS_DE_PRUEBA = [
    ("Sitio Bueno", "https://www.google.com"),
    ("Error Servidor", "https://httpbin.org/status/500"),
    ("Sitio Lento", "https://httpbin.org/delay/10"),
    ("Dominio Falso", "https://esto-no-existe-91827465.com"),
    ("Puerto Cerrado", "http://127.0.0.1:9999"),
    ("Página Inexistente", "https://www.google.com/pagina-que-no-existe"),
]


def conectar():
    conexion = sqlite3.connect(NOMBRE_BASE_DATOS)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def fecha_utc_actual():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def inicializar_base_de_datos():
    with conectar() as conexion:
        conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                interval_sec INTEGER NOT NULL DEFAULT 60,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY,
                service_id INTEGER NOT NULL REFERENCES services(id),
                checked_at TEXT NOT NULL,
                status_code INTEGER,
                response_ms INTEGER,
                ok INTEGER NOT NULL,
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_checks_service_time
            ON checks(service_id, checked_at);
            """
        )


def cargar_servicios_de_prueba():
    with conectar() as conexion:
        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM services"
        ).fetchone()[0]

        if cantidad > 0:
            print("Los servicios de prueba ya estaban cargados.")
            return

        servicios_con_fecha = [
            (nombre, url, fecha_utc_actual())
            for nombre, url in SERVICIOS_DE_PRUEBA
        ]

        conexion.executemany(
            """
            INSERT INTO services (name, url, created_at)
            VALUES (?, ?, ?)
            """,
            servicios_con_fecha,
        )

        print("Servicios de prueba cargados correctamente.")

def obtener_servicios_activos():
    with conectar() as conexion:
        cursor = conexion.execute(
            """
            SELECT id, name, url
            FROM services
            WHERE active = 1
            ORDER BY id
            """
        )

        return cursor.fetchall()


def guardar_verificacion(service_id, resultado):
    with conectar() as conexion:
        conexion.execute(
            """
            INSERT INTO checks (
                service_id,
                checked_at,
                status_code,
                response_ms,
                ok,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                service_id,
                fecha_utc_actual(),
                resultado["status_code"],
                resultado["response_ms"],
                int(resultado["ok"]),
                resultado["error"],
            ),
        )




if __name__ == "__main__":
    inicializar_base_de_datos()
    cargar_servicios_de_prueba()