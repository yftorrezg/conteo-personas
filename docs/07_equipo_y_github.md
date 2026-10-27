# 07 · Trabajo en equipo y GitHub 🤝

Cómo compartir el repositorio con el grupo de Robótica, cómo estudiar el proyecto y cómo **no subir contraseñas**.

---

## 🔒 Regla número 1: las contraseñas NO van a GitHub

Un repositorio compartido (y más si es público) **no** debe contener:
- contraseña de la Pi, del hotspot o del WiFi de casa
- el archivo `pi/wifi.env`
- llaves SSH (`id_ed25519`, **nunca** la privada)

Ya está protegido en `.gitignore`: `pi/wifi.env` y `docs/CREDENCIALES.local.md` **no se suben**. Las contraseñas se pasan al grupo por un canal privado (mensaje directo), no por el repositorio.

Plantilla para tu archivo privado: copia `docs/CREDENCIALES.local.md.example` a `docs/CREDENCIALES.local.md` y llénalo.

---

## 👤 Para el dueño del repositorio

### Subir el proyecto por primera vez
```bash
cd ~/Proyectos/conteo-personas
git init
git add .
git status                 # REVISA que no aparezca wifi.env ni CREDENCIALES.local.md
git commit -m "Sistema de conteo de personas con Raspberry Pi"
git branch -M main
```
Con la herramienta `gh` (ya instalada y con sesión iniciada):
```bash
# Privado (recomendado: solo ve quien tú invites)
gh repo create conteo-personas --private --source=. --push
```
Sin `gh`: crea un repositorio vacío en <https://github.com/new>, y luego:
```bash
git remote add origin https://github.com/TU_USUARIO/conteo-personas.git
git push -u origin main
```

### Dar acceso a tus compañeros
En GitHub: repositorio → **Settings → Collaborators → Add people** → escribe el usuario o correo de cada compañero → ellos aceptan la invitación por correo.
O desde la terminal:
```bash
gh api -X PUT repos/TU_USUARIO/conteo-personas/collaborators/USUARIO_COMPAÑERO -f permission=push
```
| Permiso | Puede |
|---|---|
| `pull` (Read) | Solo ver y descargar |
| `push` (Write) | Además subir cambios |

> 📷 Las imágenes de `docs/img/` muestran a personas. Si el repositorio fuera público, revisa que todos estén de acuerdo.

### Actualizar después de cambios
```bash
git add .
git commit -m "Describe qué cambiaste"
git push
```

---

## 🎓 Para los compañeros

### Descargar el proyecto (una vez)
```bash
git clone https://github.com/TU_USUARIO/conteo-personas.git
cd conteo-personas
```

### Traer las últimas actualizaciones
```bash
git pull
```

### ¿Por dónde empiezo a estudiar?
| Orden | Documento | Tiempo |
|---|---|---|
| 1 | `README.md` | 5 min |
| 2 | `docs/01_resumen_y_conceptos.md` (la teoría) | 20 min |
| 3 | `docs/00_GUIA_PASO_A_PASO.md` (cómo se usa) | 20 min |
| 4 | `docs/02_codigo_explicado.md` (el código) | 30 min |
| 5 | `docs/04_calibracion_y_pruebas.md` + `docs/05_guion_demo.md` | 20 min |

Lo ideal: que **cada integrante sepa encender, conectarse por SSH y apagar** la Pi (doc 00), por si el dueño del equipo no está.

### Probar el código en su propia laptop (sin Pi)
```bash
python -m venv ~/venvs/conteo
~/venvs/conteo/bin/pip install ultralytics opencv-python-headless flask
cd src
~/venvs/conteo/bin/python main.py --source ../videos/vtest.avi --show
```
Abrir luego `http://localhost:5000`. (Windows: `venv\Scripts\python main.py ...`.)

### Hacer un cambio sin romper nada (ramas)
```bash
git checkout -b mi-mejora        # crea tu rama
# ...editas...
git add .
git commit -m "Mejora X"
git push -u origin mi-mejora
```
Luego en GitHub, **Compare & pull request** para que el equipo lo revise antes de unirlo a `main`.

---

## 📋 Comandos de Git que necesitas
| Comando | Qué hace |
|---|---|
| `git status` | Qué cambió |
| `git diff` | Ver los cambios línea por línea |
| `git add .` | Marca todo para guardar |
| `git commit -m "mensaje"` | Guarda un punto en el historial |
| `git push` | Sube a GitHub |
| `git pull` | Baja de GitHub |
| `git log --oneline` | Historial resumido |
| `git checkout -b nombre` | Crea una rama |

## 🧯 Si subiste una contraseña por error
1. **Cámbiala ya** (la Pi con `passwd`, el hotspot en el celular). Borrar el archivo NO basta: queda en el historial.
2. Avisa a tus compañeros. Si el repositorio es privado el riesgo es menor.
