# Cómo usar este perfil

El README del perfil es solo una imagen animada, en versión clara y oscura. La genera
`scripts/generate.py` a partir de `profile.toml`, y un GitHub Action la regenera todos los días
con tus stats reales.

Hay tres estilos; se elige con `[perfil] estilo`:

- **`pipboy`** (el actual): pantalla CRT de fósforo con la estética de las interfaces de Fallout:
  scanlines, brillo, franja de refresco, pestañas, lista S.P.E.C.I.A.L. con tus habilidades,
  medidores y barra de nivel. Código en `scripts/pipboy.py`.
- **`widgets`**: tarjetas monocromáticas tipo pantalla de inicio, con calendario,
  frase escrita a mano, racha, contribuciones en un display LCD, cuenta regresiva, progreso del
  mes y del año, lenguajes y el gato del logo con hojas cayendo. Código en `scripts/widgets.py`.
- **`kitty`**: una terminal kitty con tres splits (`fastfetch`, `bat stack.toml`, `gh stats`).
  Código en `scripts/generate.py`.

## Publicarlo

1. En GitHub, creá un repo **público** con el mismo nombre que tu usuario (`usuario/usuario`).
   GitHub muestra su `README.md` en tu perfil.
2. En `profile.toml`, poné tu usuario de GitHub en `[perfil] usuario` (de ahí salen las stats).
   El nombre que se muestra en la interfaz va aparte, en `[perfil] nombre`.
3. Subí esta carpeta a ese repo:
   ```bash
   git init -b main
   git add .
   git commit -m "perfil animado"
   git remote add origin https://github.com/USUARIO/USUARIO.git
   git push -u origin main
   ```
4. El push dispara el workflow `Regenerar terminal`, que reemplaza los SVG de ejemplo
   por unos con tus datos. Si falla con un error de permisos: *Settings → Actions → General →
   Workflow permissions → Read and write permissions*.

## Qué se edita y dónde

Estilo `pipboy`:

| Querés cambiar | Dónde |
|---|---|
| Título y subtítulo de arriba | `[pipboy] titulo`, `subtitulo` |
| Color del fósforo (verde, ambar, azul, blanco) | `[pipboy] color_oscuro` (tema oscuro de GitHub) y `color_claro` (tema claro) |
| Lista S.P.E.C.I.A.L. (hasta 7, de 1 a 10) | `[pipboy] special` |
| El dibujo del centro | `[pipboy] personaje`: `animacion` (cuadros de un GIF), `imagen` (un PNG), `vaultboy` (dibujado a mano) o `logo` (el gato de `[fastfetch] logo`) |

Qué muestra con datos de GitHub: el número grande son las contribuciones del último año; los
medidores, racha (escala de 30 días), % de días activos del año, estrellas y seguidores (escala
de 100); la barra de abajo, repos, nivel (años programando, con la barra de XP como avance del
año) y días activos de la semana. Las pestañas INV, DATA, MAP y RADIO son decorativas.

Para cambiar la animación por otro GIF (una figura clara sobre fondo oscuro):

```bash
uv run --with pillow python scripts/trazar.py ruta/al.gif assets/source/walk
```

Deja un PNG por cuadro y `frames.json` con los tiempos del GIF; el generador los alterna en loop
con esos tiempos. Si los trazos internos salen muy finos o muy gruesos, probá `--umbral` (default
70). Cada cuadro suma unos 8 KB al SVG; con 18 cuadros queda en ~190 KB.

Vault Boy, Pip-Boy y RobCo son de Bethesda. El dibujo de `vaultboy` es fan art hecho a mano en
`vault_boy()`, no una imagen copiada. Si preferís no usar sus marcas en el perfil público,
cambiá el título y subtítulo y poné `personaje = "logo"`.

Estilo `widgets`:

| Querés cambiar | Dónde |
|---|---|
| Texto grande del calendario | `[widgets] titulo` |
| Frase escrita a mano (hasta 4 líneas cortas) | `[widgets] frase` |
| Globo de diálogo del gato | `[widgets] saludo` (vacío para sacarlo) |
| Fecha y nombre de la cuenta regresiva | `[widgets] cuenta_regresiva` |
| El dibujo del gato | `[fastfetch] logo` (`█ ▀ ▄` se dibujan como píxeles) |
| Colores | `PALETTES` en `scripts/widgets.py` |

Qué muestra cada tarjeta con datos de GitHub:

| Tarjeta | Dato |
|---|---|
| Puntos sobre los días del calendario | Contribuciones de cada uno de los últimos 7 días |
| Racha actual | Días seguidos con contribuciones (si hoy todavía no hubo, cuenta hasta ayer) |
| Display LCD y barritas | Contribuciones del último año y por semana (últimas 26) |
| Ícono de barras | Proporción de los 3 lenguajes principales |
| Pastilla "Activo" | % de días del año en curso con alguna contribución |
| Pastilla "Semana" | Días con contribuciones en los últimos 7 |
| Chips de abajo | Lenguajes principales |

Estilo `kitty`:

| Querés cambiar | Dónde |
|---|---|
| Tema (catppuccin, tokyonight, gruvbox, rosepine) | `[kitty] tema` |
| Pestañas de arriba | `[kitty] pestanas` |
| Lo que se tipea al final con el cursor parpadeando | `[kitty] comando_final` |
| Logo de fastfetch | `[fastfetch] logo` |
| Líneas de fastfetch | `[fastfetch] info` |
| El TOML que muestra `bat` | secciones `[stack.*]` |

En los dos: los lenguajes que no querés contar van en `[stats] excluir_lenguajes`.

## Generarlo en tu máquina

```bash
py scripts/generate.py --demo                  # datos de [demo], sin red
py scripts/generate.py --static --out preview  # sin animación, para mirar el resultado final
GITHUB_TOKEN=$(gh auth token) py scripts/generate.py   # stats reales completas
```

Sin token, el script usa la API REST pública: no hay contribuciones ni datos por día (esas
tarjetas muestran "—") y los lenguajes se cuentan por repo en vez de por bytes. Con token usa
GraphQL y sale todo.

Para verlo como queda en GitHub, abrí `preview/index.html` en el navegador: muestra las versiones
oscura y clara a 896 px, el ancho de la columna del perfil, con los fondos de GitHub y un botón
para repetir la animación. Después de regenerar, recargá la página. La carpeta `preview/` está
en `.gitignore` y no se sube.

## Fuentes

El SVG se muestra como `<img>`, así que no puede cargar fuentes de afuera: usa las del sistema
de quien lo mira.

- **widgets:** los números grandes son de 7 segmentos dibujados con polígonos, así que se ven
  igual en todos lados. La frase usa una letra manuscrita del sistema (Segoe Print en Windows,
  Bradley Hand en Mac); en otros sistemas cae a la cursiva por defecto.
- **kitty:** usa la monoespaciada del visitante y fuerza la grilla con `textLength`, así que todo
  queda alineado igual. Para fijar JetBrains Mono, dejá los `.woff2` en `assets/fonts/` (un archivo
  con `Bold` en el nombre se usa para la negrita) y regenerá. Se incrustan en base64 y cada peso
  suma unos 90 KB a cada SVG.

## Contribuciones privadas

El token del Action solo ve lo público. Para contar también lo privado, creá un token personal
(classic, scope `read:user`) y guardalo como secret `PROFILE_TOKEN` en el repo; el workflow lo
prefiere si existe.

## Cómo está hecho

- **Claro / oscuro:** el README usa `<picture>` + `prefers-color-scheme` para alternar entre
  `perfil-dark.svg` y `perfil-light.svg`.
- **Animación:** SMIL dentro del SVG (`<set>`, `<animate>`, `<animateMotion>`); GitHub no permite
  JS, pero sí esto. En pipboy, la pantalla se enciende desde una línea al centro, el fósforo
  parpadea apenas, una franja de refresco baja en loop y la selección recorre la lista sola. En widgets, las tarjetas entran escalonadas, la frase se destapa con un
  `clipPath` y las hojas siguen una curva en loop. En kitty, el tipeo es un `clipPath` que crece
  de a una celda y el cursor sigue la misma línea de tiempo.
- **El Action** corre todos los días y solo commitea si cambió el SVG. Como el calendario (o la
  barra de estado de kitty) muestra la fecha, en la práctica eso es un commit por día.
