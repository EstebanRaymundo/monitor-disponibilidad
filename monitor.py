import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


CARPETA_PROYECTO = Path(__file__).parent
ARCHIVO_SERVICIOS = CARPETA_PROYECTO / "services.json"
CARPETA_DATOS = CARPETA_PROYECTO / "data"
ARCHIVO_CHECKS = CARPETA_DATOS / "checks.jsonl"
ARCHIVO_ESTADO = CARPETA_DATOS / "status.json"

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


def guardar_checks(nuevos_checks):
    CARPETA_DATOS.mkdir(exist_ok=True)

    with ARCHIVO_CHECKS.open("a", encoding="utf-8") as archivo:
        for check in nuevos_checks:
            archivo.write(json.dumps(check, ensure_ascii=False) + "\n")


def guardar_estado(estado):
    CARPETA_DATOS.mkdir(exist_ok=True)

    with ARCHIVO_ESTADO.open("w", encoding="utf-8") as archivo:
        json.dump(estado, archivo, ensure_ascii=False, indent=2)


def main():
    logging.info("Iniciando monitor de disponibilidad.")

    servicios = cargar_servicios()
    nuevos_checks = []
    estado_actual = []

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

        estado_actual.append(
            {
                "id": servicio["id"],
                "name": servicio["name"],
                "url": servicio["url"],
                **nuevo_check,
            }
        )

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

    guardar_estado(
        {
            "generated_at": fecha_utc_actual(),
            "services": estado_actual,
        }
    )

    logging.info("Se guardaron %s verificaciones.", len(nuevos_checks))


if __name__ == "__main__":
    main()