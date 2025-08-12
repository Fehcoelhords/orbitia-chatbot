import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- CONFIGURAÇÕES IMPORTANTES ---

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'

# IMPORTANTE: Verifique se o seu ID da agenda está correto aqui
CALENDAR_ID = 'b521c3de1e593d32ba12ff24667e37d611bf6c7f9886827186a2f65b1d721836@group.calendar.google.com' 


def build_calendar_service():
    """
    Autentica com a API do Google e constrói o objeto de serviço do Calendar.
    """
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service


def check_availability(service, start_time, end_time):
    """
    Verifica se um horário está disponível na agenda.
    Retorna True se estiver livre, False se estiver ocupado.
    """
    # ---- ESTA É A CORREÇÃO ----
    # Adicionamos o fuso horário (-03:00 para São Paulo) no formato que a API exige.
    start_time_str = start_time.isoformat() + '-03:00'
    end_time_str = end_time.isoformat() + '-03:00'

    print(f"Verificando disponibilidade de {start_time_str} até {end_time_str}...")
    
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time_str,
        timeMax=end_time_str,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])

    if not events:
        print("Horário disponível!")
        return True
    else:
        print("Horário ocupado.")
        return False


def create_event(service, summary, start_time, end_time):
    """
    Cria um novo evento (agendamento) na agenda.
    """
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    print(f"Evento criado com sucesso: {created_event.get('htmlLink')}")
    return created_event