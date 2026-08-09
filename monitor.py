import time

import requests

from database import (
    guardar_verificacion,
    inicializar_base_de_datos,
    obtener_servicios_activos,
)


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
            timeout=5,
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


def imprimir_resultado(nombre, resultado):
    if resultado["status_code"] is not None:
        simbolo = "✓" if resultado["ok"] else "✗"

        print(
            f"{simbolo} {nombre}: "
            f"{resultado['status_code']} "
            f"{resultado['response_ms']} ms"
        )
    else:
        print(f"✗ {nombre}: -- {resultado['error'].upper()}")


if __name__ == "__main__":
    inicializar_base_de_datos()
    servicios = obtener_servicios_activos()

    for service_id, nombre, url in servicios:
        resultado = verificar_url(url)

        guardar_verificacion(service_id, resultado)
        imprimir_resultado(nombre, resultado)