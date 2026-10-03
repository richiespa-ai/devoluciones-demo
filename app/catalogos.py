"""Listas cerradas que usan la API, el formulario y el generador de datos."""

ESCUELAS = {
    "Digital": ["Máster en Marketing Digital", "Curso de Análisis de Datos", "Programa de UX/UI"],
    "FP": ["FP Administración y Finanzas", "FP Desarrollo de Aplicaciones Web", "FP Comercio Internacional"],
    "Oposiciones": ["Oposiciones Administrativo del Estado", "Oposiciones Policía Nacional", "Oposiciones Maestro de Primaria"],
    "Salud": ["Curso de Nutrición Clínica", "Técnico en Farmacia", "Curso de Auxiliar de Enfermería"],
    "Idiomas": ["Inglés B2 intensivo", "Inglés C1 para profesionales", "Alemán A2"],
}

ORIGENES = ["Email", "Chat", "Teléfono", "Formulario web"]

MOTIVOS = [
    "Motivos económicos",
    "No cumple expectativas",
    "Falta de tiempo",
    "Problemas técnicos",
    "Error en la compra",
    "Motivos personales",
    "Otros",
]

ESTADOS = ["Abierta", "En gestión", "Cerrada"]

# Resultado de una solicitud cerrada
ACCIONES = ["Devolución total", "Devolución parcial", "Retenido", "Baja sin devolución"]
ACCIONES_CON_DEVOLUCION = {"Devolución total", "Devolución parcial"}

AGENTES = ["Lucía Martín", "Andrés Gil", "Marta Ruiz", "Pablo Ortega"]

COMERCIALES = ["Carmen Vidal", "Jorge Navarro", "Elena Castro", "Raúl Prieto", "Sara Molina", "Iván Romero"]

METODOS_PAGO = ["Tarjeta", "Transferencia", "PayPal", "Financiación"]
