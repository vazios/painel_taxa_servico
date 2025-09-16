import pytz
from datetime import datetime

API_REPORT = "https://report.yooga.com.br/delivery/relatorio"
API_FIDELITY = "https://fidelity-api.yooga.com.br/api/v1/fidelity/list?filter=ACTIVE&user_id="
API_PAYMENTS = "https://report.yooga.com.br/payments/list"
TIMEZONE = pytz.timezone("America/Sao_Paulo")