import json
import datetime
import httpx
from typing import Optional
from app.config import settings
from app.schemas import AIDecisionSchema, AICustomerReplySchema, DiagnosisType, RecommendedActionType, CustomerReplyIntent

class LLMService:
    @staticmethod
    def get_diagnosis_fallback(failure_code: str) -> DiagnosisType:
        """
        Deterministic diagnosis mapping from failure codes.
        """
        code = (failure_code or "").upper()
        if "INSUFFICIENT" in code or "BALANCE" in code or "FUNDS" in code:
            return DiagnosisType.INSUFFICIENT_FUNDS
        elif "EXPIRED" in code or "EXPIRY" in code:
            return DiagnosisType.EXPIRED_PAYMENT_METHOD
        elif "GATEWAY" in code or "TIMEOUT" in code or "DOWN" in code or "NETWORK" in code or "ACQUIRER" in code or "SYSTEM" in code:
            return DiagnosisType.TRANSIENT_GATEWAY_ERROR
        elif "LIMIT" in code or "EXCEED" in code or "MAX" in code:
            return DiagnosisType.LIMIT_EXCEEDED
        elif "PIN" in code or "OTP" in code or "FRICT" in code or "SECURE" in code or "DECLINE" in code:
            return DiagnosisType.CUSTOMER_FRICTION
        elif "ABANDON" in code or "CHECKOUT" in code:
            return DiagnosisType.CHECKOUT_ABANDONMENT
        return DiagnosisType.UNKNOWN

    @staticmethod
    def get_action_fallback(diagnosis: DiagnosisType, attempt_count: int) -> tuple[RecommendedActionType, int]:
        """
        Deterministic recovery action mapping. Returns (action_type, delay_hours).
        """
        if diagnosis == DiagnosisType.TRANSIENT_GATEWAY_ERROR:
            # Immediate retry on first failure, wait for second
            if attempt_count == 0:
                return RecommendedActionType.RETRY_PAYMENT, 0
            else:
                return RecommendedActionType.WAIT_AND_RETRY, 2
        elif diagnosis == DiagnosisType.INSUFFICIENT_FUNDS:
            # Re-attempting balance card charge fails, ask customer via link
            return RecommendedActionType.CREATE_PAYMENT_LINK, 24
        elif diagnosis == DiagnosisType.EXPIRED_PAYMENT_METHOD:
            # Expired cards cannot be charged, require new method link
            return RecommendedActionType.CREATE_PAYMENT_LINK, 1
        elif diagnosis == DiagnosisType.LIMIT_EXCEEDED:
            return RecommendedActionType.CREATE_PAYMENT_LINK, 24
        elif diagnosis == DiagnosisType.CUSTOMER_FRICTION:
            return RecommendedActionType.CREATE_PAYMENT_LINK, 2
        elif diagnosis == DiagnosisType.CHECKOUT_ABANDONMENT:
            return RecommendedActionType.SEND_NOTIFICATION, 4
        return RecommendedActionType.CREATE_PAYMENT_LINK, 12

    @staticmethod
    def get_message_fallback(
        diagnosis: DiagnosisType, 
        action: RecommendedActionType, 
        customer_name: str, 
        amount: float,
        payment_link: str = None
    ) -> str:
        """
        Generates contextual messages using professional templates.
        """
        link_str = f" Pay here: {payment_link}" if payment_link else ""
        if diagnosis == DiagnosisType.INSUFFICIENT_FUNDS:
            return (
                f"Hi {customer_name}, we tried to process your payment of ₹{amount:,.2f} for your subscription, "
                f"but it was declined by your bank. To avoid service disruption, please secure your payment method or pay here:{link_str}"
            )
        elif diagnosis == DiagnosisType.EXPIRED_PAYMENT_METHOD:
            return (
                f"Hi {customer_name}, it looks like your card on file for your payment of ₹{amount:,.2f} has expired. "
                f"Please update your card info or pay directly using this secure link:{link_str}"
            )
        elif diagnosis == DiagnosisType.CHECKOUT_ABANDONMENT:
            return (
                f"Hi {customer_name}, we noticed you left items in your cart. You can complete your secure checkout "
                f"of ₹{amount:,.2f} directly by clicking here:{link_str}"
            )
        return (
            f"Hi {customer_name}, we encountered an issue processing your payment of ₹{amount:,.2f}. "
            f"Please complete it securely using the following link:{link_str}"
        )

    @classmethod
    def diagnose_and_recommend(
        cls,
        payment_context: dict,
        customer_context: dict,
        attempt_count: int
    ) -> AIDecisionSchema:
        """
        Diagnoses payment failure and recommends recovery action.
        Calls Gemini API if settings.LLM_API_KEY is present; otherwise falls back to rule-based engine.
        """
        api_key = settings.LLM_API_KEY
        
        failure_code = payment_context.get("failure_code", "UNKNOWN")
        amount = payment_context.get("amount", 0.0)
        cust_name = customer_context.get("name", "Customer")
        
        # Rule-based fallback calculations
        fallback_diagnosis = cls.get_diagnosis_fallback(failure_code)
        fallback_action, delay_hours = cls.get_action_fallback(fallback_diagnosis, attempt_count)
        fallback_msg = cls.get_message_fallback(fallback_diagnosis, fallback_action, cust_name, amount)

        if not api_key:
            # Return rule-based fallback if API key is not configured
            return AIDecisionSchema(
                diagnosis=fallback_diagnosis,
                confidence=0.85,
                recommended_action=fallback_action,
                delay_hours=delay_hours,
                reason="Rule-based fallback: No LLM API key configured.",
                message_intent="payment_recovery",
                message_content=fallback_msg
            )

        # Call Gemini API
        system_prompt = (
            "You are a fintech AI agent tasked with diagnosing payment failures and selecting recovery actions.\n"
            "Respond ONLY with a structured JSON object matching this schema:\n"
            "{\n"
            '  "diagnosis": "TRANSIENT_GATEWAY_ERROR" | "INSUFFICIENT_FUNDS" | "EXPIRED_PAYMENT_METHOD" | "LIMIT_EXCEEDED" | "CUSTOMER_FRICTION" | "CHECKOUT_ABANDONMENT" | "UNKNOWN",\n'
            '  "confidence": float (between 0.0 and 1.0),\n'
            '  "recommended_action": "RETRY_PAYMENT" | "CREATE_PAYMENT_LINK" | "WAIT_AND_RETRY" | "SEND_NOTIFICATION" | "ESCALATE" | "NO_ACTION",\n'
            '  "delay_hours": int (delay before executing recommended action),\n'
            '  "reason": "short explanation of the diagnosis and recommendation reasoning",\n'
            '  "message_intent": "payment_recovery",\n'
            '  "message_content": "concise, helpful, non-threatening customer-facing notification text"\n'
            "}"
        )
        
        user_prompt = f"""
        Payment Context: {json.dumps(payment_context)}
        Customer Context: {json.dumps(customer_context)}
        Attempt History:
        - Current Attempt Count: {attempt_count}
        
        Analyze the failure code and context, determine the diagnosis and best strategy, and output JSON.
        """

        try:
            url = f"https://generativetoolkit.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": f"System Context:\n{system_prompt}\n\nUser Input:\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            
            # Use httpx for REST call
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                res_json = res.json()
                
                # Parse response content
                candidates = res_json.get("candidates", [])
                if not candidates:
                    raise RuntimeError("No candidates returned from Gemini API")
                    
                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed_decision = json.loads(text_content.strip())
                
                # Validate with Pydantic
                return AIDecisionSchema(**parsed_decision)

        except Exception as e:
            # Fallback to rule-based decision on LLM failure
            print(f"[LLMService Error]: LLM call failed. Error: {e}. Falling back to rule-based decision.", flush=True)
            return AIDecisionSchema(
                diagnosis=fallback_diagnosis,
                confidence=0.75,
                recommended_action=fallback_action,
                delay_hours=delay_hours,
                reason=f"LLM failure fallback: {str(e)}",
                message_intent="payment_recovery",
                message_content=fallback_msg
            )

    @classmethod
    def interpret_customer_reply(cls, reply_text: str) -> AICustomerReplySchema:
        """
        Interprets customer text response to identify intent (Promise-to-pay, dispute, opt-out).
        Calls Gemini API if settings.LLM_API_KEY is present; otherwise falls back to rule-based logic.
        """
        api_key = settings.LLM_API_KEY
        text = reply_text.lower().strip()

        # Fallback interpretation logic
        intent = CustomerReplyIntent.OTHER
        promised_date = None
        reason = "Rule-based reply interpretation fallback."
        
        # Check opt-out
        if any(w in text for w in ["stop", "opt out", "unsubscribe", "don't message", "dont message", "quit"]):
            intent = CustomerReplyIntent.OPT_OUT
            reason = "Detected opt-out keywords."
        # Check dispute
        elif any(w in text for w in ["dispute", "unauthorized", "chargeback", "fraud", "not mine", "didn't buy", "didnt buy"]):
            intent = CustomerReplyIntent.DISPUTE
            reason = "Detected dispute keywords."
        # Check promise to pay
        elif any(w in text for w in ["pay", "friday", "monday", "tomorrow", "next week", "promised", "salary", "date", "weekend"]):
            intent = CustomerReplyIntent.PROMISE_TO_PAY
            # Calculate a mock promise date (e.g. 3 days from now)
            future_date = datetime.date.today() + datetime.timedelta(days=3)
            promised_date = future_date.isoformat()
            reason = f"Detected payment promise keywords. Scheduled promise date to: {promised_date}."

        if not api_key:
            return AICustomerReplySchema(
                intent=intent,
                promised_date=promised_date,
                confidence=0.85,
                reason=reason
            )

        # Call Gemini API for NLP classification
        system_prompt = (
            "You are a fintech AI agent. Interpret a customer reply to determine their intent:\n"
            "Respond ONLY with a structured JSON object matching this schema:\n"
            "{\n"
            '  "intent": "PROMISE_TO_PAY" | "DISPUTE" | "OPT_OUT" | "OTHER",\n'
            '  "promised_date": "YYYY-MM-DD" or null (only extract ISO date if intent is PROMISE_TO_PAY and they mention a date/day/time. If they say tomorrow or a day, calculate it relative to current date 2026-08-30),\n'
            '  "confidence": float (between 0.0 and 1.0),\n'
            '  "reason": "brief reason explaining classification decision"\n'
            "}"
        )
        
        user_prompt = f"Customer Reply: \"{reply_text}\""

        try:
            url = f"https://generativetoolkit.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": f"System Context:\n{system_prompt}\n\nUser Input:\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                res_json = res.json()
                
                candidates = res_json.get("candidates", [])
                if not candidates:
                    raise RuntimeError("No candidates returned from Gemini API")
                    
                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed_reply = json.loads(text_content.strip())
                
                return AICustomerReplySchema(**parsed_reply)

        except Exception as e:
            print(f"[LLMService Error]: Customer reply interpretation failed. Error: {e}. Falling back.", flush=True)
            return AICustomerReplySchema(
                intent=intent,
                promised_date=promised_date,
                confidence=0.70,
                reason=f"NLP call failed fallback: {str(e)}"
            )
