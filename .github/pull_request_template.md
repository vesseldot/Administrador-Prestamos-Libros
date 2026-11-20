## Descripción

<!-- Qué cambia y por qué. Enlaza el issue si existe: "Cierra #12". -->

## Tipo de cambio

- [ ] `feat`: nueva funcionalidad
- [ ] `fix`: corrección
- [ ] `docs`: documentación
- [ ] `refactor` / `test` / `chore`

## Cómo se probó

<!-- Pasos para reproducir y comandos ejecutados. -->

- [ ] `python -m pytest tests` pasa
- [ ] Probé la aplicación con `python main.py` (si cambia la interfaz o el comportamiento)
- [ ] Agregué o actualicé pruebas cuando correspondía

## Lista de verificación

- [ ] La rama base es `develop` (o `main` solo para correcciones urgentes)
- [ ] Respeta el contrato de [INTEGRACION.md](../INTEGRACION.md): `ui/` solo usa la API pública del servicio (`tests/test_arquitectura.py` pasa)
- [ ] Si toca archivos de backend o `ui/tareas.py`, se coordinó con el responsable de backend
- [ ] No incluye `.env`, `secrets/`, llaves, `chroma_db/`, modelos, registros ni datos personales reales
- [ ] No hay valores de configuración nuevos fuera de `config.py` / `.env.example`
- [ ] La documentación está actualizada (README, ARQUITECTURA, SEGURIDAD) si aplica
- [ ] Si cambia el modelo de embeddings o el esquema de Redis, está documentada la migración

## Capturas (opcional)

<!-- Para cambios visuales, tomadas con `python demo_interfaz.py` (datos ficticios). -->

