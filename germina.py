import os
import speech_recognition as sr
import win32com.client
from dotenv import load_dotenv
from datetime import datetime
import time
from groq import Groq

# 1. Cargar las variables del archivo .env
load_dotenv()

# 2. Leer la API Key desde el entorno
api_key_groq = os.getenv("GROQ_API_KEY")

# 3. Usarla para el cliente
client = Groq(api_key=api_key_groq)


fecha_actual = datetime.now().strftime("%A, %d de %B de %Y")

# Historial para que Germina tenga memoria (Groq usa una lista de mensajes)
historial = [
    {"role": "system", "content": f"Eres Germina, un asistente de voz rápido y eficiente. Hoy es {fecha_actual}. Responde de forma concisa y fluida."}
]

speaker = win32com.client.Dispatch("SAPI.SpVoice")
interrumpido = False

# Función para hablar
def speak(text):
    global interrumpido
    interrumpido = False
    print(f"Germina: {text}")
    # Flags: 1 (Asíncrono, no congela Python) y 2 (Limpia audios anteriores)
    speaker.Speak(text, 1 | 2)

    # Nueva función para escuchar interrupciones rápidas mientras habla
def listen_for_interrupt(recognizer, source):
    global interrumpido
    try:
        # Aumentamos un poco el umbral solo durante la interrupción
        # para que ignore el volumen de fondo de los altavoces
        recognizer.energy_threshold = 1500 
        
        audio = recognizer.listen(source, timeout=2, phrase_time_limit=1)
        command = recognizer.recognize_google(audio, language='es-ES').lower()
        
        palabras_corte = ["cállate", "para", "detente", "basta"]
        if any(palabra in command for palabra in palabras_corte):
            print("\n[¡Interrupción detectada!]")
            interrumpido = True
            speaker.Speak("", 1 | 2)
    except:
        pass
    finally:
        # Volvemos a la sensibilidad normal para cuando TÚ hables
        recognizer.energy_threshold = 300

# Función para escuchar
def listen(recognizer, source):
    print("\n[Ajustando ruido de fondo...]")
    recognizer.adjust_for_ambient_noise(source, duration=0.8)
    print("Escuchando...")
    try:
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
        command = recognizer.recognize_google(audio, language='es-ES')
        return command.lower()
    except Exception:
        return ""

# Programa principal
def main():
    global interrumpido
    recognizer = sr.Recognizer()

    # Abrimos el micrófono una sola vez aquí para que ambas funciones lo usen
    with sr.Microphone() as source:
        speak("Hola, soy tu asistente de voz Germina. que se lo ofrece")
        time.sleep(3.5) # Espera a que termine el saludo para no escucharse a sí misma
        

        while True:
            # Le pasamos el recognizer y source activos
            pregunta = listen(recognizer, source)
            if pregunta:
                print(f"Tú dijiste: {pregunta}")

                if "salir" in pregunta or "adiós" in pregunta:
                    speaker.Speak("Hasta luego, que tengas un buen día.", 1 | 2)
                    time.sleep(2)
                    break
                try:
                    # Agregamos lo que dijiste al historial
                    historial.append({"role": "user", "content": pregunta})

                    # Llamada a Groq
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=historial
                    )

                    respuesta_ai = completion.choices[0].message.content
                    
                    # Guardamos la respuesta para que tenga memoria
                    historial.append({"role": "assistant", "content": respuesta_ai})
                    
                    respuesta_limpia = respuesta_ai.replace('*', '').replace('_', '')

                    # Hilo para hablar mientras seguimos atentos a interrupciones
                    hilo_voz = threading.Thread(target=speak, args=(respuesta_limpia,))
                    hilo_voz.start()

                    while speaker.Status.RunningState == 2:
                        listen_for_interrupt(recognizer, source)
                        if interrumpido:
                            break
                        time.sleep(0.1)

                except Exception as e:
                    print(f"Error: {e}")
                    speak("Hubo un error al procesar tu petición con Groq.")
                
try:
    # 1. Añadimos lo que dijiste al historial
    historial.append({"role": "user", "content": pregunta})

    # 2. Llamada a Groq
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile", # El modelo más potente de Groq actualmente
        messages=historial,
        temperature=0.7,
        max_tokens=3024,
    )

    respuesta_ai = completion.choices[0].message.content
    
    # 3. Guardamos la respuesta de la IA en el historial para que recuerde la charla
    historial.append({"role": "assistant", "content": respuesta_ai})

    # Limpiamos caracteres extraños para que SAPI no se trabe
    respuesta_limpia = respuesta_ai.replace('*', '').replace('_', '')
    
    # Ejecutar el habla en el hilo que ya tenías
    hilo_voz = threading.Thread(target=speak, args=(respuesta_limpia,))
    hilo_voz.start()

    # Monitor de interrupción (Igual que antes)
    while speaker.Status.RunningState == 2:
        listen_for_interrupt(recognizer, source)
        if interrumpido:
            break
        time.sleep(0.1)

except Exception as e:
    print(f"Error en Groq: {e}")
    speak("Hubo un fallo en mi conexión ultra rápida.")


# Ejecutar programa
if __name__ == "__main__":
    main()