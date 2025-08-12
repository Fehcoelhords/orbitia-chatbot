import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta

# ---- NOVA IMPORTAÇÃO ----
# Importamos as funções que criamos no nosso outro arquivo
import google_calendar_manager as calendar

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# Configura a API do Gemini
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("A chave da API do Gemini não foi encontrada no arquivo .env")
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    raise ValueError(f"Erro ao configurar a API do Gemini. Verifique sua chave: {e}")

# ---- NOVO OBJETO ----
# "Abre a porta" para o Google Calendar assim que o app inicia
calendar_service = calendar.build_calendar_service()

SESSIONS = {} 

# O "CÉREBRO" DO BOT: O CONTEXTO REFINADO PARA A IA
CONTEXTO_SALAO = """
Você é o Orbit IA, um assistente virtual do salão "Beleza Total".
Sua personalidade: Você é amigável, direto e eficiente. Fale como uma pessoa, não como um robô. Evite repetir saudações como "Olá!" em todas as frases.
Suas diretrizes:
1.  Lembre-se do Contexto: Se um cliente menciona um serviço (ex: hidratação), lembre-se disso nas próximas perguntas. Não pergunte de novo o que já foi dito.
2.  Seja Proativo: Se o cliente parece interessado em um serviço, pergunte diretamente se ele quer agendar.
3.  Responda a Perguntas Gerais: Use seu conhecimento para responder sobre serviços, preços (se souber), horários e endereço de forma natural.
4.  Lide com Perguntas Fora do Escopo: Se perguntarem algo que não tem a ver com o salão (ex: "comer pão"), responda de forma curta e educada, trazendo a conversa de volta ao foco. Ex: "Isso eu não consigo te ajudar, mas posso agendar um horário para você ficar ainda mais bonita(o)!"
5.  Identidade: Se perguntarem quem você é, diga que é o Orbit IA, o assistente virtual do Beleza Total, criado para facilitar o agendamento e tirar dúvidas.
"""

def reset_session(session_id):
    if session_id in SESSIONS:
        SESSIONS.pop(session_id, None)
    return "Tudo bem! Se precisar de algo mais, é só chamar."

def get_session(session_id):
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {'estado': 'inicial', 'dados_agendamento': {}}
    return SESSIONS[session_id]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    user_message = data['message'].strip()
    user_message_lower = user_message.lower() 
    session_id = data.get('session_id', 'default_session')

    session = get_session(session_id)
    estado_atual = session['estado']
    dados_agendamento = session['dados_agendamento']

    palavras_de_cancelamento = ['cancelar', 'cancela', 'não quero', 'deixa pra lá', 'parar']
    if any(palavra in user_message_lower for palavra in palavras_de_cancelamento):
        return jsonify({"response": reset_session(session_id)})

    if estado_atual == 'pedindo_nome':
        if any(kw in user_message_lower for kw in ['serviços', 'horários', 'disponíveis', 'preços']):
             pass
        else:
            dados_agendamento['nome'] = user_message.title()
            session['estado'] = 'pedindo_data_hora'
            servico = dados_agendamento.get('servico', '')
            return jsonify({"response": f"Perfeito, {dados_agendamento['nome']}! Para qual data e hora você gostaria de agendar seu {servico}? (Ex: 11/08 às 10:00)"})

    # --- PARTE MAIS IMPORTANTE E MODIFICADA ---
    if estado_atual == 'pedindo_data_hora':
        match = re.search(r'(\d{1,2}[/-]\d{1,2}).*(às|as|h)\s*(\d{1,2}(?::\d{2})?)', user_message_lower)
        if match:
            # 1. Extrai a data e hora da mensagem do usuário
            data_str = match.group(1).replace('-', '/')
            hora_str = match.group(3)
            if ':' not in hora_str: hora_str += ':00'
            
            try:
                # 2. Converte o texto em objetos de data/hora reais
                start_time_obj = datetime.strptime(f"{data_str}/2025 {hora_str}", '%d/%m/%Y %H:%M')
                # Assume que cada serviço dura 1 hora
                end_time_obj = start_time_obj + timedelta(hours=1)
                
                # 3. CHAMA A VERIFICAÇÃO DE DISPONIBILIDADE
                is_available = calendar.check_availability(calendar_service, start_time_obj, end_time_obj)

                if is_available:
                    # 4. SE ESTIVER LIVRE, CRIA O EVENTO
                    nome_cliente = dados_agendamento.get('nome', 'Cliente')
                    servico = dados_agendamento.get('servico', 'serviço').title()
                    titulo_evento = f"{servico} - {nome_cliente}"

                    calendar.create_event(calendar_service, titulo_evento, start_time_obj, end_time_obj)
                    
                    response_text = f"Agendamento confirmado! Seu {servico.lower()} com {nome_cliente} no dia {start_time_obj.strftime('%d/%m/%Y')} às {start_time_obj.strftime('%H:%M')} foi realizado com sucesso!"
                    reset_session(session_id) 
                    return jsonify({"response": response_text})
                else:
                    # 5. SE ESTIVER OCUPADO, AVISA O USUÁRIO
                    return jsonify({"response": "Puxa, este horário já está ocupado. Por favor, escolha outro horário."})

            except ValueError:
                return jsonify({"response": "O formato da data ou da hora parece incorreto. Por favor, tente novamente no formato 'DD/MM às HH:MM'."})
        else:
            return jsonify({"response": "Não consegui entender a data e a hora. Por favor, tente usar um formato como '11/08 às 10:00'."})

    palavras_de_agendamento = ['agendar', 'marcar', 'reservar', 'horário']
    servicos_disponiveis = ['corte', 'manicure', 'pedicure', 'hidratação']
    servico_mencionado = next((s for s in servicos_disponiveis if s in user_message_lower), None)

    if any(palavra in user_message_lower for palavra in palavras_de_agendamento):
        if servico_mencionado:
            dados_agendamento['servico'] = servico_mencionado
            session['estado'] = 'pedindo_nome'
            return jsonify({"response": f"Claro! Para agendarmos seu {servico_mencionado}, por favor, me diga seu nome completo."})
        else:
            if 'servico' in dados_agendamento:
                session['estado'] = 'pedindo_nome'
                return jsonify({"response": f"Ok! Para agendarmos seu {dados_agendamento['servico']}, qual o seu nome completo?"})
            pass 

    try:
        if servico_mencionado and 'servico' not in dados_agendamento:
             dados_agendamento['servico'] = servico_mencionado
        model = genai.GenerativeModel(model_name='gemini-1.5-flash-latest', system_instruction=CONTEXTO_SALAO)
        response = model.generate_content(user_message)
        return jsonify({"response": response.text})
    except Exception as e:
        print(f"ERRO CRÍTICO NA API DA GEMINI: {e}") 
        resposta_de_fallback = "Peço desculpas, estou com uma instabilidade no sistema. No momento, consigo apenas ajudar com agendamentos ou fornecer informações sobre nossos serviços. Como posso te ajudar com isso?"
        return jsonify({"response": resposta_de_fallback})

if __name__ == '__main__':
    app.run(debug=True)