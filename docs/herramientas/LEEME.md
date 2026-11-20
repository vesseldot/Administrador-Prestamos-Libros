# Generación de los PDF de la documentación

Los archivos Markdown de `docs/` son las **fuentes editables**. Los PDF se generan a partir de ellos con `generar_pdf.py`. Cuando cambies un Markdown, regenera el PDF correspondiente en el mismo commit.

| PDF | Fuentes |
|---|---|
| `GUIA_TECNICA_COLABORADORES.pdf` | `GUIA_TECNICA_COLABORADORES.md` y, como anexos A–H, `ARQUITECTURA.md`, `FLUJOS_DATOS.md`, `MODELO_SEMANTICO.md`, `SEGURIDAD.md`, `../INTEGRACION.md`, `INSTALACION.md`, `CONTRIBUCION.md` y `MANTENIMIENTO.md` |
| `GUIA_ESTUDIO_PROYECTO.pdf` | `GUIA_ESTUDIO_PROYECTO.md` |
| `INFORME_LIMPIEZA_Y_DOCUMENTACION.pdf` | `INFORME_LIMPIEZA_Y_DOCUMENTACION.md` |

## Requisitos

- **pandoc 3.x**: <https://pandoc.org/installing.html>. Probado con 3.8.
- **Google Chrome** o **Microsoft Edge**. El script los busca en las rutas habituales de Windows y en el `PATH`. Probado con Chrome 157.
- Paquetes de Python (no forman parte de `requirements.txt`, porque la aplicación no los usa):
  ```powershell
  pip install -r docs/herramientas/requisitos.txt
  ```
- Conexión a Internet **solo la primera vez**: se descarga `mermaid.min.js` 11.4.1 desde jsDelivr, se comprueba su huella SHA-256 y se guarda en la carpeta temporal del sistema (`%TEMP%\biblioteca-docs`).

## Uso

```powershell
python docs/herramientas/generar_pdf.py                  # los tres PDF
python docs/herramientas/generar_pdf.py guia_estudio     # solo uno: guia_tecnica, guia_estudio o informe
python docs/herramientas/generar_pdf.py --conservar-html # conserva el HTML intermedio para revisarlo
```

## Cómo funciona

1. Cada Markdown se convierte a HTML con pandoc (`gfm`), con resaltado de sintaxis.
2. Los bloques `mermaid` se dibujan con mermaid.js dentro del navegador. En los diagramas de secuencia, los mensajes largos se parten por los espacios para que quepan en la página. El Markdown no se modifica.
3. Los enlaces entre documentos incluidos en el mismo PDF se convierten en enlaces internos. Los enlaces a otros archivos del repositorio apuntan a GitHub (rama `develop`).
4. El navegador sin ventana imprime el cuerpo en tamaño carta, con encabezado, pie y «Página X de Y». Se hacen dos pasadas: la primera localiza la página de cada capítulo y la segunda escribe el índice con esos números.
5. pypdf une la portada y el cuerpo, añade los metadatos y conserva los marcadores de navegación.

El script avisa si un enlace interno no tiene destino, si un capítulo no aparece en el índice o si un diagrama queda reducido por debajo del 60 % de su tamaño (texto de menos de unos 7 pt).
