from database import conectar


def mostrar_resultados():
    with conectar() as conexion:
        resultados = conexion.execute(
            """
            SELECT
                s.name,
                c.ok,
                c.status_code,
                c.error,
                c.response_ms,
                c.checked_at
            FROM checks AS c
            JOIN services AS s ON s.id = c.service_id
            ORDER BY c.id
            """
        ).fetchall()

    for nombre, ok, codigo, error, tiempo, fecha in resultados:
        codigo_mostrado = codigo if codigo is not None else "--"
        error_mostrado = error if error is not None else "--"
        tiempo_mostrado = f"{tiempo} ms" if tiempo is not None else "--"

        print(
            f"{nombre}: "
            f"ok={ok}, "
            f"codigo={codigo_mostrado}, "
            f"error={error_mostrado}, "
            f"tiempo={tiempo_mostrado}, "
            f"utc={fecha}"
        )


if __name__ == "__main__":
    mostrar_resultados()