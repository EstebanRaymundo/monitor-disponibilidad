import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


CARPETA_PROYECTO = Path(__file__).parent
ARCHIVO_SERVICIOS = CARPETA_PROYECTO / "services.json"
CARPETA_DATOS = CARPETA_PROYECTO / "data"
CARPETA_DOCS = CARPETA_PROYECTO / "docs"
ARCHIVO_CHECKS = CARPETA_DATOS / "checks.jsonl"
ARCHIVO_ESTADO = CARPETA_DATOS / "status.json"
ARCHIVO_ESTADO_DOCS = CARPETA_DOCS / "status.json"
CARPETA_ARCHIVO = CARPETA_DATOS / "archive"

TIMEOUT_SEGUNDOS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def fecha_utc_actual():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def es_error_dns(error):
    mensaje = str(error).lower()

    indicadores_dns = [
        "getaddrinfo failed",
        "name or service not known",
        "nodename nor servname provided",
        "could not resolve",
        "failed to resolve",
    ]

    return any(indicador in mensaje for indicador in indicadores_dns)


def verificar_url(url):
    inicio = time.monotonic()

    try:
        respuesta = requests.get(
            url,
            timeout=TIMEOUT_SEGUNDOS,
            headers={"User-Agent": "MonitorDisponibilidad/1.0"},
        )

        duracion_ms = round((time.monotonic() - inicio) * 1000)

        return {
            "ok": 200 <= respuesta.status_code < 400,
            "status_code": respuesta.status_code,
            "response_ms": duracion_ms,
            "error": None,
        }

    except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
        return {
            "ok": False,
            "status_code": None,
            "response_ms": None,
            "error": "timeout",
        }

    except requests.exceptions.ConnectionError as error:
        tipo_error = "dns" if es_error_dns(error) else "connection"

        return {
            "ok": False,
            "status_code": None,
            "response_ms": None,
            "error": tipo_error,
        }

    except requests.exceptions.RequestException:
        return {
            "ok": False,
            "status_code": None,
            "response_ms": None,
            "error": "other",
        }


def cargar_servicios():
    with ARCHIVO_SERVICIOS.open(encoding="utf-8") as archivo:
        servicios = json.load(archivo)

    if not isinstance(servicios, list) or not servicios:
        raise ValueError("services.json debe contener una lista con servicios.")

    return servicios


def rotar_checks_antiguos():
    if not ARCHIVO_CHECKS.exists():
        return

    limite = datetime.now(timezone.utc) - timedelta(days=30)
    checks_recientes = []
    checks_por_mes = {}

    with ARCHIVO_CHECKS.open(encoding="utf-8") as archivo:
        for linea in archivo:
            if not linea.strip():
                continue

            check = json.loads(linea)
            fecha_check = datetime.fromisoformat(check["checked_at"])

            if fecha_check < limite:
                nombre_mes = fecha_check.strftime("%Y-%m")
                checks_por_mes.setdefault(nombre_mes, []).append(check)
            else:
                checks_recientes.append(check)

    if not checks_por_mes:
        logging.info("No hay verificaciones antiguas para archivar.")
        return

    CARPETA_ARCHIVO.mkdir(parents=True, exist_ok=True)

    for nombre_mes, checks in checks_por_mes.items():
        archivo_mes = CARPETA_ARCHIVO / f"{nombre_mes}.jsonl"

        with archivo_mes.open("a", encoding="utf-8") as archivo:
            for check in checks:
                archivo.write(json.dumps(check, ensure_ascii=False) + "\n")

    with ARCHIVO_CHECKS.open("w", encoding="utf-8") as archivo:
        for check in checks_recientes:
            archivo.write(json.dumps(check, ensure_ascii=False) + "\n")

    logging.info(
        "Se archivaron %s verificaciones antiguas.",
        sum(len(checks) for checks in checks_por_mes.values()),
    )


def cargar_todos_los_checks():
    if not ARCHIVO_CHECKS.exists():
        return []

    checks = []
    with ARCHIVO_CHECKS.open(encoding="utf-8") as archivo:
        for linea in archivo:
            if linea.strip():
                try:
                    checks.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue
    return checks


def guardar_checks(nuevos_checks):
    CARPETA_DATOS.mkdir(exist_ok=True)

    with ARCHIVO_CHECKS.open("a", encoding="utf-8") as archivo:
        for check in nuevos_checks:
            archivo.write(json.dumps(check, ensure_ascii=False) + "\n")


def generar_y_guardar_status(servicios):
    checks_totales = cargar_todos_los_checks()
    ahora = datetime.now(timezone.utc)
    hace_24h = ahora - timedelta(hours=24)
    hace_7d = ahora - timedelta(days=7)
    hace_1h = ahora - timedelta(hours=1)

    servicios_resultado = []

    for servicio in servicios:
        s_id = servicio["id"]
        s_checks = [c for c in checks_totales if c.get("service_id") == s_id]

        if not s_checks:
            servicios_resultado.append(
                {
                    "id": s_id,
                    "name": servicio["name"],
                    "url": servicio["url"],
                    "current": "unknown",
                    "last_checked": None,
                    "uptime_24h": None,
                    "uptime_7d": None,
                    "avg_response_ms": None,
                    "recent": [],
                }
            )
            continue

        s_checks.sort(key=lambda x: x["checked_at"], reverse=True)
        ultimo_check = s_checks[0]
        fecha_ultimo = datetime.fromisoformat(ultimo_check["checked_at"])

        if fecha_ultimo < hace_1h:
            current = "unknown"
        else:
            current = "up" if ultimo_check["ok"] else "down"

        checks_24h = [
            c for c in s_checks if datetime.fromisoformat(c["checked_at"]) >= hace_24h
        ]
        checks_7d = [
            c for c in s_checks if datetime.fromisoformat(c["checked_at"]) >= hace_7d
        ]

        if checks_24h:
            exitosos_24h = sum(1 for c in checks_24h if c["ok"])
            uptime_24h = round((exitosos_24h / len(checks_24h)) * 100, 2)
        else:
            uptime_24h = None

        if checks_7d:
            exitosos_7d = sum(1 for c in checks_7d if c["ok"])
            uptime_7d = round((exitosos_7d / len(checks_7d)) * 100, 2)
        else:
            uptime_7d = None

        exitosas_resp = [
            c["response_ms"]
            for c in checks_24h
            if c["ok"] and c.get("response_ms") is not None
        ]
        if exitosas_resp:
            avg_response_ms = round(sum(exitosas_resp) / len(exitosas_resp))
        else:
            avg_response_ms = None

        ultimas_60 = s_checks[:60]
        recent = [1 if c["ok"] else 0 for c in reversed(ultimas_60)]

        servicios_resultado.append(
            {
                "id": s_id,
                "name": servicio["name"],
                "url": servicio["url"],
                "current": current,
                "last_checked": ultimo_check["checked_at"],
                "uptime_24h": uptime_24h,
                "uptime_7d": uptime_7d,
                "avg_response_ms": avg_response_ms,
                "recent": recent,
            }
        )

    status_data = {
        "generated_at": fecha_utc_actual(),
        "services": servicios_resultado,
    }

    CARPETA_DATOS.mkdir(exist_ok=True)
    CARPETA_DOCS.mkdir(exist_ok=True)

    with ARCHIVO_ESTADO.open("w", encoding="utf-8") as archivo:
        json.dump(status_data, archivo, ensure_ascii=False, indent=2)

    with ARCHIVO_ESTADO_DOCS.open("w", encoding="utf-8") as archivo:
        json.dump(status_data, archivo, ensure_ascii=False, indent=2)


def main():
    logging.info("Iniciando monitor de disponibilidad.")

    servicios = cargar_servicios()
    rotar_checks_antiguos()
    nuevos_checks = []

    for servicio in servicios:
        resultado = verificar_url(servicio["url"])
        checked_at = fecha_utc_actual()

        nuevo_check = {
            "service_id": servicio["id"],
            "checked_at": checked_at,
            "status_code": resultado["status_code"],
            "response_ms": resultado["response_ms"],
            "ok": resultado["ok"],
            "error": resultado["error"],
        }

        nuevos_checks.append(nuevo_check)

        logging.info(
            "%s - ok=%s - status=%s - error=%s",
            servicio["name"],
            resultado["ok"],
            resultado["status_code"],
            resultado["error"],
        )

    if not nuevos_checks:
        logging.error("No se escribió ningún resultado.")
        raise SystemExit(1)

    guardar_checks(nuevos_checks)
    generar_y_guardar_status(servicios)

    logging.info("Se guardaron %s verificaciones.", len(nuevos_checks))


if __name__ == "__main__":
    main()