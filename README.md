# SoloBoom LAS — ranking en vivo

Página que trackea el SoloQ de 4 jugadores de LAS y se actualiza sola cada 30 minutos,
usando la **API oficial de Riot Games** (no lee op.gg directamente, porque op.gg no lo permite).

Cómo funciona: un GitHub Action corre cada 30 minutos, le pregunta a Riot el rango actual
de cada jugador (`fetch_data.py`) y guarda el resultado en `data.json`. La página
(`index.html`) lee ese archivo y dibuja el ranking. Todo gratis, sin servidor propio.

## 1. Conseguí una API key de Riot

1. Entrá a **https://developer.riotgames.com** e iniciá sesión con tu cuenta de Riot.
2. Arriba a la derecha vas a ver tu **Development API Key** — copiala. Sirve para probar,
   pero **expira cada 24 horas**.
3. Para que no se corte el tracker, pedí una **Personal API Key** desde el mismo panel
   (botón "Register Product" → Personal API Key). Es gratis, pero la aprobación puede
   tardar un par de días. Mientras tanto arrancá con la Development Key y después
   reemplazá el secret cuando te aprueben la personal.

## 2. Subí este proyecto a un repo de GitHub

1. Creá un repositorio nuevo y **público** en GitHub (tiene que ser público para poder
   usar GitHub Pages gratis).
2. Subí todos los archivos de esta carpeta manteniendo la estructura, incluida la carpeta
   `.github/workflows/`.

## 3. Cargá la API key como secret

1. En el repo: **Settings → Secrets and variables → Actions → New repository secret**.
2. Nombre: `RIOT_API_KEY`. Valor: la key que copiaste en el paso 1.

## 4. Activá GitHub Pages

1. **Settings → Pages**.
2. En "Source" elegí **Deploy from a branch**, branch `main`, carpeta `/ (root)`.
3. Guardá. En un par de minutos tu página va a estar en
   `https://tu-usuario.github.io/tu-repo/`.

## 5. Disparalo por primera vez

No hace falta esperar a que se cumplan los 30 minutos: andá a la pestaña **Actions**,
entrá al workflow "Actualizar ranking SoloBoom LAS" y tocá **Run workflow**. Si todo
salió bien, en un minuto va a aparecer un commit nuevo con `data.json` actualizado y
la página va a mostrar los rangos reales.

## Agregar, sacar o corregir jugadores

Editá `players.json`. Cada jugador necesita su Riot ID separado en `gameName` y
`tagLine` (lo que va antes y después del `#`, tal cual figura en su op.gg). No hace
falta tocar ningún otro archivo.

## Cosas para tener en cuenta

- **La Development Key expira todos los días.** Si el Action empieza a fallar, es lo
  primero para chequear: entrá a developer.riotgames.com, generá una nueva y
  actualizá el secret `RIOT_API_KEY`.
- **GitHub no garantiza el minuto exacto** de un cron programado — normalmente corre
  a los pocos minutos del horario pactado, pero en momentos de mucha carga puede
  demorarse un poco más.
- Si falla la consulta de un jugador puntual (nombre mal escrito, caída momentánea de
  la API), el script no borra sus datos: deja el último dato bueno marcado como
  "desactualizado" en vez de mostrar la tarjeta vacía.
- El "progreso desde que arrancamos a trackear" queda fijado la primera vez que el
  Action corre con éxito. Si querés resetear el punto de partida de todos, borrá el
  campo `"baseline"` de cada jugador en `data.json` y esperá a la próxima corrida.

## Probarlo en tu computadora

Como `script.js` usa `fetch()`, abrir `index.html` haciendo doble clic no va a
funcionar (los navegadores bloquean `fetch` sobre archivos locales). Corré un
servidor simple desde la carpeta del proyecto:

```bash
python3 -m http.server 8000
```

y abrí `http://localhost:8000` en el navegador.
