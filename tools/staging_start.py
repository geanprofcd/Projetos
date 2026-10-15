"""Inicia H1-005B9 somente na copia STAGING localhost:8011."""
from tools.staging_runtime import load

def main():
    load()
    import uvicorn
    print('VENDRA-STAGING H1-005B9 - SIMULACOES SEM META/MAKE/WHATSAPP/ENVIO.')
    uvicorn.run('app.staging_h1_005b9:app',host='127.0.0.1',port=8011,
                log_level='info',access_log=False)

if __name__=='__main__':main()
