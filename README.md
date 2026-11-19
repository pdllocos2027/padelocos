# PADELOCOS — sitio web funcional

Incluye agenda pública ordenada por fecha, inscripción solo con nombre, lista pública de jugadores, límite de cupos, precios editables y panel privado para crear, editar y eliminar partidos y jugadores.

## Ejecutar localmente

1. Instala Python 3.10 o superior.
2. En esta carpeta ejecuta `pip install -r requirements.txt`.
3. Configura dos variables de entorno ANTES del primer inicio:
   - `SECRET_KEY`: cadena aleatoria larga (ej. `python -c "import secrets;print(secrets.token_hex(32))"`)
   - `ADMIN_PASSWORD`: contraseña privada y fuerte que elijas.
4. Ejecuta `python app.py`.
5. Abre `http://127.0.0.1:5000` y entra por «Administración».

Ejemplo macOS/Linux:
```
export SECRET_KEY='CAMBIA_POR_UNA_CADENA_ALEATORIA'
export ADMIN_PASSWORD='CAMBIA_POR_TU_CONTRASENA'
python app.py
```

Ejemplo PowerShell:
```
$env:SECRET_KEY='CAMBIA_POR_UNA_CADENA_ALEATORIA'
$env:ADMIN_PASSWORD='CAMBIA_POR_TU_CONTRASENA'
python app.py
```

El primer arranque crea el administrador con la contraseña proporcionada. Para cambiarla después hay que actualizar el hash de contraseña de la base de datos; cambiar solo la variable no cambia una contraseña ya creada.

## Publicación

El ZIP es el código fuente, **no una página publicada**. Para ponerlo en internet se necesita alojamiento con Python y una base de datos persistente, HTTPS, variables de entorno seguras y copias de seguridad. No utilices el servidor de desarrollo de Flask como servidor público. SQLite funciona para despliegues pequeños con almacenamiento persistente; en servicios con disco efímero se perderán los datos. Para producción conviene añadir limitación de intentos de inicio de sesión, protección antispam de inscripciones y políticas de privacidad (los nombres son públicos).

El formulario solo solicita nombre; personas con el mismo nombre no pueden registrarse dos veces en el mismo partido. Sin cuentas no puede verificarse la identidad de quien escribe un nombre. Los partidos pasados dejan de aparecer en la agenda pública, pero siguen disponibles en Administración.
