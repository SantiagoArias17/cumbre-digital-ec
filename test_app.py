"""
Pruebas automáticas del servidor Flask de Cumbre Digital EC 2026.

Ejecutar (con el ambiente virtual activo):
    python -m unittest -v
"""

import os
import tempfile
import unittest

import app as servidor


# Datos válidos de ejemplo para reutilizar en las pruebas
ASISTENTE_VALIDO = {
    "nombre": "María Fernanda López",
    "email": "maria@ejemplo.com",
    "empresa": "Innova PyME S.A.",
    "area": "Tecnología",
}


class PruebasRegistro(unittest.TestCase):

    def setUp(self):
        """Antes de cada prueba: base de datos temporal y vacía (no toca evento.db)."""
        descriptor, self.ruta_bd = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.ruta_original = servidor.RUTA_BD
        servidor.RUTA_BD = self.ruta_bd
        servidor.inicializar_bd()
        self.cliente = servidor.app.test_client()

    def tearDown(self):
        """Después de cada prueba: restaura la ruta y borra la base temporal."""
        servidor.RUTA_BD = self.ruta_original
        os.remove(self.ruta_bd)

    def registrar(self, **cambios):
        """Envía el formulario con los datos válidos más los cambios indicados."""
        return self.cliente.post("/registrar", data={**ASISTENTE_VALIDO, **cambios})

    # ===== Páginas =====

    def test_formulario_carga(self):
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Registro de asistentes", respuesta.text)

    def test_admin_vacio(self):
        respuesta = self.cliente.get("/admin")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Aún no hay asistentes registrados", respuesta.text)

    def test_confirmacion_inexistente_da_404(self):
        respuesta = self.cliente.get("/confirmacion/REG-9999")
        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("Página no encontrada", respuesta.text)

    # ===== Registro correcto =====

    def test_registro_valido_redirige_a_confirmacion(self):
        respuesta = self.registrar()
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/confirmacion/REG-0001"))

        confirmacion = self.cliente.get("/confirmacion/REG-0001")
        self.assertEqual(confirmacion.status_code, 200)
        self.assertIn("¡Registro confirmado!", confirmacion.text)
        self.assertIn("María Fernanda López", confirmacion.text)

    def test_numeros_de_registro_consecutivos(self):
        self.registrar()
        respuesta = self.registrar(email="otro@ejemplo.com")
        self.assertTrue(respuesta.headers["Location"].endswith("/confirmacion/REG-0002"))

    def test_registro_aparece_en_admin(self):
        self.registrar()
        respuesta = self.cliente.get("/admin")
        self.assertIn("maria@ejemplo.com", respuesta.text)
        self.assertIn("REG-0001", respuesta.text)

    def test_email_se_guarda_en_minusculas(self):
        self.registrar(email="  MARIA@Ejemplo.COM ")
        self.assertIn("maria@ejemplo.com", self.cliente.get("/admin").text)

    # ===== Errores de validación =====

    def test_email_duplicado(self):
        self.registrar()
        respuesta = self.registrar(email="MARIA@ejemplo.com")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Este email ya está registrado", respuesta.text)

    def test_campos_vacios(self):
        respuesta = self.registrar(nombre="", email="", empresa="", area="")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Por favor, ingresa tu nombre completo.", respuesta.text)
        self.assertIn("Por favor, ingresa tu email.", respuesta.text)
        self.assertIn("Por favor, ingresa tu empresa u organización.", respuesta.text)
        self.assertIn("Por favor, selecciona un área de interés.", respuesta.text)

    def test_nombre_muy_corto(self):
        respuesta = self.registrar(nombre="Al")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("al menos 3 caracteres", respuesta.text)

    def test_email_con_formato_invalido(self):
        respuesta = self.registrar(email="correo-sin-arroba")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no tiene un formato válido", respuesta.text)

    def test_area_fuera_de_la_lista(self):
        respuesta = self.registrar(area="Deportes")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("El área seleccionada no es válida.", respuesta.text)

    def test_datos_se_conservan_tras_error(self):
        respuesta = self.registrar(email="malo")
        self.assertIn('value="María Fernanda López"', respuesta.text)

    def test_registro_invalido_no_se_guarda(self):
        self.registrar(nombre="")
        self.assertIn("Aún no hay asistentes registrados", self.cliente.get("/admin").text)

    # ===== Seguridad =====

    def test_html_se_escapa(self):
        self.registrar(nombre="<script>alert(1)</script>")
        respuesta = self.cliente.get("/confirmacion/REG-0001")
        self.assertNotIn("<script>alert(1)</script>", respuesta.text)
        self.assertIn("&lt;script&gt;", respuesta.text)


if __name__ == "__main__":
    unittest.main()
