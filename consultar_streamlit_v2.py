# Archivo: consultar_streamlit_v2.py
# Motor de búsqueda y síntesis v2 con Descomposición de Consulta.
# Esta versión es segura y está diseñada para ser subida a un repositorio público de GitHub.

import streamlit as st
import google.generativeai as genai
import pandas as pd
import chromadb
import re

# --- CONFIGURACIÓN (sin clave de API hardcodeada) ---
NOMBRE_DB = 'base_de_datos_blog'
NOMBRE_COLECCION = 'posts'
NUM_RESULTADOS_POR_TERMINO = 5 # Cuántos resultados buscar por cada concepto clave

def cargar_recursos():
    """
    Carga todos los recursos pesados leyendo la clave de API desde los secretos de Streamlit.
    Esta función se cachea para ejecutarse solo una vez por sesión.
    """
    print("Cargando recursos v2 (leyendo secretos)...")
    
    # Leemos la clave de API de forma segura desde los secretos de Streamlit
    try:
        # st.secrets funciona como un diccionario. Buscamos la clave "GOOGLE_API_KEY".
        api_key_secreta = st.secrets["GOOGLE_API_KEY"]
    except (KeyError, FileNotFoundError):
        # Si la clave no está configurada en Streamlit Cloud, mostramos un error claro en la app.
        st.error("ERROR: La clave 'GOOGLE_API_KEY' no se ha configurado en los secretos de Streamlit.")
        st.stop() # Detiene la ejecución de la app si la clave no está

    genai.configure(api_key=api_key_secreta)
    model = genai.GenerativeModel('models/gemini-flash-latest')
    
    client = chromadb.PersistentClient(path=NOMBRE_DB)
    collection = client.get_collection(name=NOMBRE_COLECCION)
    df = pd.read_csv('datos_para_gem_COMPLETO_FINAL.csv').fillna('')
    print("Recursos v2 cargados con éxito.")
    return model, collection, df

def obtener_terminos_clave(pregunta, model):
    """
    Usa Gemini para extraer las entidades y conceptos clave de la pregunta.
    """
    prompt = f"""
    De la siguiente pregunta de usuario, extrae los 2 o 3 conceptos o entidades más importantes para realizar una búsqueda en una base de datos.
    Devuelve solo los términos, separados por comas. No añadas explicaciones ni texto introductorio.
    Ejemplo 1:
    Pregunta: cual es la relacion entre sv17q y milorbs?
    Respuesta: sv17q, milorbs
    Ejemplo 2:
    Pregunta: hablame mas sobre el programa medron y su autor
    Respuesta: programa medron, autor
    
    Pregunta a analizar: "{pregunta}"
    Respuesta:
    """
    response = model.generate_content(prompt)
    terminos = [term.strip() for term in response.text.split(',')]
    print(f"  - Conceptos clave identificados por IA: {terminos}")
    return terminos

def realizar_busqueda_avanzada(terminos, collection, df):
    """
    Realiza múltiples búsquedas (una por cada término) y unifica los resultados.
    """
    contexto_final = ""
    chunks_usados = set()
    urls_usadas = set()
    placeholder_text = '[Sin contenido principal en inglés o párrafos muy cortos]'

    for termino in terminos:
        print(f"    - Buscando información sobre: '{termino}'...")
        # Búsqueda semántica para el término
        resultados_semanticos = collection.query(query_texts=[termino], n_results=NUM_RESULTADOS_POR_TERMINO)
        
        # Búsqueda por palabra clave para el término (regex=False para una búsqueda simple y rápida)
        resultados_clave_df = df[df['contenido_chunk'].str.contains(termino, case=False, regex=False)]

        # Unificamos resultados para este término
        for i in range(len(resultados_semanticos['ids'][0])):
            chunk = resultados_semanticos['documents'][0][i]
            if chunk != placeholder_text and chunk not in chunks_usados:
                meta = resultados_semanticos['metadatas'][0][i]
                contexto_final += f"--- Fragmento (sobre '{termino}') de: {meta['url']} ---\nContenido: {chunk}\n\n"
                chunks_usados.add(chunk)
                urls_usadas.add(meta['url'])

        for index, row in resultados_clave_df.head(NUM_RESULTADOS_POR_TERMINO).iterrows():
            chunk = row['contenido_chunk']
            if chunk not in chunks_usados and chunk != placeholder_text:
                contexto_final += f"--- Fragmento (sobre '{termino}') de: {row['url']} ---\nContenido: {chunk}\n\n"
                chunks_usados.add(chunk)
                urls_usadas.add(row['url'])
                
    return contexto_final, sorted(list(urls_usadas))

def generar_respuesta_final(pregunta, contexto, historial, model):
    """
    Toma la pregunta original y el contexto unificado para generar la respuesta final.
    """
    historial_gemini = []
    for msg in historial:
        role = 'user' if msg['role'] == 'user' else 'model'
        historial_gemini.append({'role': role, 'parts': [msg['content']]})

    chat = model.start_chat(history=historial_gemini)
    
    prompt_para_este_turno = f"""
    Considerando nuestra conversación anterior, responde a la pregunta original del usuario de forma completa y exhaustiva.
    Tu única fuente de verdad es el siguiente contexto, que ha sido recopilado de múltiples búsquedas sobre los conceptos clave de la pregunta.
    Analiza TODOS los fragmentos y conecta las ideas para sintetizar la respuesta más completa posible.

    PREGUNTA ORIGINAL DEL USUARIO: "{pregunta}"

    CONTEXTO RECOPILADO DE LA BASE DE DATOS:
    ---
    {contexto}
    ---
    RESPUESTA COMPLETA Y SINTETIZADA:
    """
    response = chat.send_message(prompt_para_este_turno)
    return response.text

