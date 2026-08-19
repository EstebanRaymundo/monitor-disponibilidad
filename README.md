# Monitor de disponibilidad

Monitor de sitios web y APIs hecho con Python. Verifica la disponibilidad de servicios, clasifica fallos de red y publica el estado actual en una página pública.

## Página pública

[Ver estado actual](https://estebanraymundo.github.io/monitor-disponibilidad/)

El archivo de estado público está disponible en:

[status.json](https://estebanraymundo.github.io/monitor-disponibilidad/status.json)

## Servicios monitoreados

- Google
- GitHub
- Wikipedia
- Python
- OpenAI

La lista se encuentra en `services.json`.

## Automatización e Intervalo Real

GitHub Actions ejecuta el monitor automáticamente mediante un evento `schedule` con la siguiente expresión cron (minutos impares para evitar congestión):

```text
3-59/5 * * * *