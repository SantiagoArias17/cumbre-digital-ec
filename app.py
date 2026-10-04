"""
Servidor Flask de Cumbre Digital EC 2026.
Registra asistentes en la base de datos SQLite evento.db.
"""

import os
import re
import sqlite3

from flask import Flask, abort, redirect, render_template, request, url_for

app = Flask(__name__)

# Ruta absoluta a la base de datos (en la raíz del proyecto)
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evento.db")

# Áreas de interés permitidas (deben coincidir con las del formulario)
AREAS = ["Tecnología", "Marketing", "Negocios", "Emprendimiento"]

# Misma expresión regular que usa la validación del navegador
REGEX_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


# ===== Base de datos =====

def conectar():
    """Abre una conexión a evento.db; las filas se leen como diccionarios."""
    conexion = sqlite3.connect(RUTA_BD)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_bd():
    """Crea la tabla de asistentes si todavía no existe."""
    with conectar() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS asistentes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_registro TEXT    UNIQUE,
                nombre          TEXT    NOT NULL,
                email           TEXT    NOT NULL UNIQUE,
                empresa         TEXT    NOT NULL,
                area            TEXT    NOT NULL CHECK (area IN ('Tecnología', 'Marketing', 'Negocios', 'Emprendimiento')),
                fecha_registro  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
    conexion.close()


# ===== Validación =====

def validar(datos):
    """Devuelve un diccionario {campo: mensaje} con los errores encontrados."""
    errores = {}

    if not datos["nombre"]:
        errores["nombre"] = "Por favor, ingresa tu nombre completo."
    elif len(datos["nombre"]) < 3:
        errores["nombre"] = "El nombre debe tener al menos 3 caracteres."

    if not datos["email"]:
        errores["email"] = "Por favor, ingresa tu email."
    elif not REGEX_EMAIL.match(datos["email"]):
        errores["email"] = "El email no tiene un formato válido (ej. nombre@dominio.com)."

    if not datos["empresa"]:
        errores["empresa"] = "Por favor, ingresa tu empresa u organización."

    if not datos["area"]:
        errores["area"] = "Por favor, selecciona un área de interés."
    elif datos["area"] not in AREAS:
        errores["area"] = "El área seleccionada no es válida."

    return errores


# ===== Rutas =====

@app.route("/")
def inicio():
    """Muestra el formulario de registro vacío."""
    return render_template("index.html", datos={}, errores={}, areas=AREAS)


@app.route("/registrar", methods=["POST"])
def registrar():
    """Valida los datos, guarda al asistente y redirige a la confirmación."""
    datos = {
        "nombre": request.form.get("nombre", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "empresa": request.form.get("empresa", "").strip(),
        "area": request.form.get("area", "").strip(),
    }

    errores = validar(datos)
    if errores:
        return render_template("index.html", datos=datos, errores=errores, areas=AREAS), 400

    conexion = conectar()
    try:
        with conexion:
            cursor = conexion.execute(
                "INSERT INTO asistentes (nombre, email, empresa, area) VALUES (?, ?, ?, ?)",
                (datos["nombre"], datos["email"], datos["empresa"], datos["area"]),
            )
            # El número de registro se deriva del id: REG-0001, REG-0002, ...
            numero = f"REG-{cursor.lastrowid:04d}"
            conexion.execute(
                "UPDATE asistentes SET numero_registro = ? WHERE id = ?",
                (numero, cursor.lastrowid),
            )
    except sqlite3.IntegrityError:
        # El único campo UNIQUE que puede repetirse aquí es el email
        errores["email"] = "Este email ya está registrado en el evento."
        return render_template("index.html", datos=datos, errores=errores, areas=AREAS), 400
    finally:
        conexion.close()

    # Patrón Post/Redirect/Get: recargar la confirmación no duplica el registro
    return redirect(url_for("confirmacion", numero_registro=numero))


@app.route("/confirmacion/<numero_registro>")
def confirmacion(numero_registro):
    """Muestra la pantalla de registro confirmado."""
    conexion = conectar()
    asistente = conexion.execute(
        "SELECT * FROM asistentes WHERE numero_registro = ?", (numero_registro,)
    ).fetchone()
    conexion.close()

    if asistente is None:
        abort(404)
    return render_template("confirmacion.html", asistente=asistente)


@app.route("/admin")
def admin():
    """Lista todos los asistentes registrados con un resumen por área."""
    conexion = conectar()
    asistentes = conexion.execute(
        "SELECT * FROM asistentes ORDER BY id DESC"
    ).fetchall()
    filas_area = conexion.execute(
        "SELECT area, COUNT(*) AS total FROM asistentes GROUP BY area"
    ).fetchall()
    conexion.close()

    # Incluye todas las áreas, aunque tengan 0 asistentes
    conteo = {area: 0 for area in AREAS}
    for fila in filas_area:
        conteo[fila["area"]] = fila["total"]

    return render_template("admin.html", asistentes=asistentes, conteo=conteo)


@app.errorhandler(404)
def no_encontrado(error):
    """Página de error 404 en español."""
    return render_template("404.html"), 404


# La tabla se crea al importar el módulo (funciona igual con gunicorn en Render)
inicializar_bd()

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=puerto, debug=True)
