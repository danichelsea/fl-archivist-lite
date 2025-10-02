# Archivo: app_v2.py
# Interfaz de usuario para el motor v2.

import streamlit as st
# Importamos nuestro nuevo motor avanzado
import consultar_streamlit_v2 as motor_v2

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Archivista de FL v2", layout="wide")

st.title("🧠 Archivista de 'Forgotten Languages' (v2)")
st.subheader("Tu asistente de investigación con IA avanzada y Descomposición de Consulta")

# --- LÓGICA DE LA APLICACIÓN ---

@st.cache_resource
def inicializar_motor():
    """Carga los recursos pesados (modelos, DB) usando la función del motor v2."""
    return motor_v2.cargar_recursos()

# Cargamos los recursos
model, collection, df = inicializar_motor()

# Inicialización de la memoria del chat
if "messages_v2" not in st.session_state:
    st.session_state.messages_v2 = []

# Mostramos el historial de mensajes
for message in st.session_state.messages_v2:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "urls" in message and message["urls"]:
            with st.expander("Fuentes Utilizadas"):
                for url in message["urls"]:
                    st.write(f"- {url}")

# Gestión de la nueva pregunta del usuario
if prompt := st.chat_input("Haz tu pregunta compleja sobre el blog..."):
    st.session_state.messages_v2.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # --- ORQUESTACIÓN DEL NUEVO FLUJO DE 3 PASOS ---

            # PASO 1: Usar Gemini para descomponer la pregunta en términos clave
            with st.spinner("Paso 1/3: Analizando los conceptos clave de tu pregunta..."):
                terminos_clave = motor_v2.obtener_terminos_clave(prompt, model)
            
            # PASO 2: Realizar la búsqueda avanzada para cada término
            with st.spinner(f"Paso 2/3: Buscando información exhaustiva sobre: `{'`, `'.join(terminos_clave)}`..."):
                contexto, urls = motor_v2.realizar_busqueda_avanzada(terminos_clave, collection, df)
            
            if not contexto:
                respuesta_texto = "No se encontró información relevante en la base de datos para esta consulta."
                urls_finales = []
            else:
                # PASO 3: Generar la respuesta final con el contexto unificado
                with st.spinner("Paso 3/3: Sintetizando la respuesta final a partir de toda la información..."):
                    respuesta_texto = motor_v2.generar_respuesta_final(prompt, contexto, st.session_state.messages_v2, model)
                    urls_finales = urls

            # Mostramos los resultados
            st.markdown(respuesta_texto)
            if urls_finales:
                with st.expander("Fuentes Utilizadas"):
                    for url in urls_finales:
                        st.markdown(f"- {url}")
            
            # Guardamos la respuesta en la memoria del chat
            st.session_state.messages_v2.append({"role": "assistant", "content": respuesta_texto, "urls": urls_finales})

        except Exception as e:
            st.error(f"Ocurrió un error inesperado durante el proceso: {e}")

# Esto es necesario si la carga inicial de recursos falla
elif not model:
    st.error("No se han podido cargar los recursos necesarios para iniciar la aplicación.")
