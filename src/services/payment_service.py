import httpx
import random
import hmac
import hashlib
from src.core.config import settings

class PaymentService:
    """
    Gerencia a comunicação com a API de pagamentos (GGPIX).
    Responsável por criar cobranças e validar webhooks.
    """

    @staticmethod
    def generate_random_cpf():
        """
        Gera um CPF válido aleatório para passar na validação da API.
        """
        def calculate_digit(digits):
            s = sum(d * w for d, w in zip(digits, range(len(digits) + 1, 1, -1)))
            r = (s * 10) % 11
            return 0 if r == 10 else r

        cpf = [random.randint(0, 9) for _ in range(9)]
        cpf.append(calculate_digit(cpf))
        cpf.append(calculate_digit(cpf))
        return "".join(map(str, cpf))

    @staticmethod
    async def create_pix_charge(amount: float, description: str, payer_name: str, external_id: str):
        """
        Cria cobrança Pix na GGPIX.
        """
        url = f"{settings.GGPIX_BASE_URL}/pix/in"
        
        amount_cents = int(amount * 100)
        
        payload = {
            "amountCents": amount_cents,
            "description": description[:50], 
            "payerName": payer_name[:50],
            "payerDocument": PaymentService.generate_random_cpf(),
            "externalId": external_id,
            "webhookUrl": f"{settings.WEBHOOK_URL}/payment-webhook"
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": settings.GGPIX_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 201:
                    return response.json()
                else:
                    print(f"Erro GGPIX: {response.text}")
                    return None
            except Exception as e:
                print(f"Erro Conexão Pix: {e}")
                return None

    @staticmethod
    async def send_pix_out(amount: float, pix_key: str, pix_type: str, external_id: str):
        """
        Realiza transferência Pix (Saque) para o usuário via GGPIX.
        """
        url = f"{settings.GGPIX_BASE_URL}/pix/out"
        amount_cents = int(amount * 100)
        
        payload = {
            "amountCents": amount_cents,
            "pixKey": pix_key,
            "pixKeyType": pix_type.upper(), 
            "externalId": external_id,
            "description": "Saque Plataforma"
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": settings.GGPIX_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=15)
                if response.status_code == 201:
                    return response.json()
                print(f"Erro Pix Out: {response.text}")
                return None
            except Exception as e:
                print(f"Erro Conexão Pix Out: {e}")
                return None

    @staticmethod
    def validate_webhook_signature(raw_body: bytes, signature: str) -> bool:
        """
        Valida se o webhook veio mesmo da GGPIX (HMAC SHA256).
        """
        if not signature or not settings.GGPIX_WEBHOOK_SECRET:
            return True 
            
        try:
            parts = signature.split(',')
            timestamp = parts[0].replace('t=', '')
            received_sig = parts[1].replace('v1=', '')
            
            signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
            
            expected_sig = hmac.new(
                settings.GGPIX_WEBHOOK_SECRET.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(received_sig, expected_sig)
        except Exception as e:
            print(f"Erro validação assinatura: {e}")
            return False