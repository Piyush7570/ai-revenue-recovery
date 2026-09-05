import random
import datetime
from typing import Dict, List, Any
from app.schemas import DiagnosisType, RecommendedActionType, PaymentType, MetricSummary, EvaluationResults

# Independent Ground Truth Dataset (50 Synthetic Cases)
# Generated with controlled distribution
SYNTHETIC_DATASET: List[Dict[str, Any]] = [
    # 25% Insufficient Funds (13 cases)
    {"id": "syn_01", "customer_name": "Rohan Sharma", "amount": 2499.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.70, "recovery_chance_retry": 0.05},
    {"id": "syn_02", "customer_name": "Aditya Verma", "amount": 1299.0, "failure_code": "INSUFFICIENT_BALANCE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.65, "recovery_chance_retry": 0.05},
    {"id": "syn_03", "customer_name": "Priya Patel", "amount": 4999.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.05},
    {"id": "syn_04", "customer_name": "Vikram Singh", "amount": 799.0, "failure_code": "BAD_BALANCE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.80, "recovery_chance_retry": 0.10},
    {"id": "syn_05", "customer_name": "Neha Gupta", "amount": 3499.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.70, "recovery_chance_retry": 0.05},
    {"id": "syn_06", "customer_name": "Siddharth Rao", "amount": 1599.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.05},
    {"id": "syn_07", "customer_name": "Amit Kumar", "amount": 2499.0, "failure_code": "LOW_BALANCE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.65, "recovery_chance_retry": 0.05},
    {"id": "syn_08", "customer_name": "Ananya Sen", "amount": 999.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.75, "recovery_chance_retry": 0.08},
    {"id": "syn_09", "customer_name": "Sanjay Dutt", "amount": 5999.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.02},
    {"id": "syn_10", "customer_name": "Deepika P.", "amount": 1299.0, "failure_code": "INSUFFICIENT_BALANCE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.70, "recovery_chance_retry": 0.05},
    {"id": "syn_11", "customer_name": "Varun Dhawan", "amount": 1999.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.05},
    {"id": "syn_12", "customer_name": "Alia Bhatt", "amount": 2999.0, "failure_code": "LOW_BALANCE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.75, "recovery_chance_retry": 0.10},
    {"id": "syn_13", "customer_name": "Karan Johar", "amount": 8999.0, "failure_code": "INSUFFICIENT_FUNDS", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.INSUFFICIENT_FUNDS, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.45, "recovery_chance_retry": 0.02},

    # 20% Transient Gateway Error (10 cases)
    {"id": "syn_14", "customer_name": "Rajesh Koothra", "amount": 1500.0, "failure_code": "GATEWAY_TIMEOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "EMAIL", "recovery_chance_link": 0.40, "recovery_chance_retry": 0.90},
    {"id": "syn_15", "customer_name": "Kunal Nayyar", "amount": 2500.0, "failure_code": "ACQUIRER_DOWN", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "SMS", "recovery_chance_link": 0.40, "recovery_chance_retry": 0.85},
    {"id": "syn_16", "customer_name": "Sheldon Cooper", "amount": 999.0, "failure_code": "NETWORK_FAILURE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.95},
    {"id": "syn_17", "customer_name": "Leonard H.", "amount": 1999.0, "failure_code": "GATEWAY_ERROR", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.90},
    {"id": "syn_18", "customer_name": "Penny Hof", "amount": 499.0, "failure_code": "GATEWAY_TIMEOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "EMAIL", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.92},
    {"id": "syn_19", "customer_name": "Howard W.", "amount": 3500.0, "failure_code": "ACQUIRER_TIMEOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "SMS", "recovery_chance_link": 0.35, "recovery_chance_retry": 0.80},
    {"id": "syn_20", "customer_name": "Bernadette R.", "amount": 1200.0, "failure_code": "NETWORK_FAILURE", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.95},
    {"id": "syn_21", "customer_name": "Amy Farrah", "amount": 2999.0, "failure_code": "GATEWAY_ERROR", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.45, "recovery_chance_retry": 0.88},
    {"id": "syn_22", "customer_name": "Stuart Bloom", "amount": 150.0, "failure_code": "ACQUIRER_DOWN", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "EMAIL", "recovery_chance_link": 0.65, "recovery_chance_retry": 0.90},
    {"id": "syn_23", "customer_name": "Leslie Winkle", "amount": 4500.0, "failure_code": "GATEWAY_TIMEOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.TRANSIENT_GATEWAY_ERROR, "expected_action": RecommendedActionType.RETRY_PAYMENT, "preferred_channel": "SMS", "recovery_chance_link": 0.30, "recovery_chance_retry": 0.85},

    # 15% Expired Card (8 cases)
    {"id": "syn_24", "customer_name": "Steve Rogers", "amount": 1499.0, "failure_code": "CARD_EXPIRED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.65, "recovery_chance_retry": 0.00},
    {"id": "syn_25", "customer_name": "Tony Stark", "amount": 9999.0, "failure_code": "EXPIRED_CARD", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.00},
    {"id": "syn_26", "customer_name": "Bruce Banner", "amount": 599.0, "failure_code": "CARD_EXPIRED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.80, "recovery_chance_retry": 0.00},
    {"id": "syn_27", "customer_name": "Thor Odinson", "amount": 3999.0, "failure_code": "EXPIRED_CARD", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.70, "recovery_chance_retry": 0.00},
    {"id": "syn_28", "customer_name": "Natasha Romanoff", "amount": 2499.0, "failure_code": "CARD_EXPIRED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.75, "recovery_chance_retry": 0.00},
    {"id": "syn_29", "customer_name": "Clint Barton", "amount": 1999.0, "failure_code": "EXPIRED_CARD", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.00},
    {"id": "syn_30", "customer_name": "Wanda Maximoff", "amount": 2999.0, "failure_code": "CARD_EXPIRED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.70, "recovery_chance_retry": 0.00},
    {"id": "syn_31", "customer_name": "Peter Parker", "amount": 399.0, "failure_code": "EXPIRED_CARD", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.EXPIRED_PAYMENT_METHOD, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.85, "recovery_chance_retry": 0.00},

    # 10% Limit Exceeded (5 cases)
    {"id": "syn_32", "customer_name": "Clark Kent", "amount": 4999.0, "failure_code": "LIMIT_EXCEEDED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.LIMIT_EXCEEDED, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.05},
    {"id": "syn_33", "customer_name": "Bruce Wayne", "amount": 89999.0, "failure_code": "CARD_LIMIT_REACHED", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.LIMIT_EXCEEDED, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.30, "recovery_chance_retry": 0.02},
    {"id": "syn_34", "customer_name": "Diana Prince", "amount": 12500.0, "failure_code": "TXN_LIMIT_EXCEEDED", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.LIMIT_EXCEEDED, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.55, "recovery_chance_retry": 0.05},
    {"id": "syn_35", "customer_name": "Barry Allen", "amount": 899.0, "failure_code": "LIMIT_EXCEEDED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.LIMIT_EXCEEDED, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.65, "recovery_chance_retry": 0.10},
    {"id": "syn_36", "customer_name": "Arthur Curry", "amount": 7500.0, "failure_code": "CARD_LIMIT_REACHED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.LIMIT_EXCEEDED, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.45, "recovery_chance_retry": 0.03},

    # 15% Checkout Abandonment (7 cases)
    {"id": "syn_37", "customer_name": "Luke Skywalker", "amount": 10500.0, "failure_code": "CHECKOUT_ABANDONED", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "EMAIL", "recovery_chance_link": 0.35, "recovery_chance_retry": 0.00},
    {"id": "syn_38", "customer_name": "Leia Organa", "amount": 4500.0, "failure_code": "ABANDONED_CHECKOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "SMS", "recovery_chance_link": 0.40, "recovery_chance_retry": 0.00},
    {"id": "syn_39", "customer_name": "Han Solo", "amount": 1500.0, "failure_code": "CHECKOUT_ABANDONED", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.00},
    {"id": "syn_40", "customer_name": "Obi-Wan Kenobi", "amount": 3200.0, "failure_code": "ABANDONED_CHECKOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.45, "recovery_chance_retry": 0.00},
    {"id": "syn_41", "customer_name": "Yoda Master", "amount": 600.0, "failure_code": "CHECKOUT_ABANDONED", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "EMAIL", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.00},
    {"id": "syn_42", "customer_name": "Anakin S.", "amount": 12500.0, "failure_code": "ABANDONED_CHECKOUT", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "SMS", "recovery_chance_link": 0.30, "recovery_chance_retry": 0.00},
    {"id": "syn_43", "customer_name": "Padme Amidala", "amount": 8900.0, "failure_code": "CHECKOUT_ABANDONED", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.CHECKOUT_ABANDONMENT, "expected_action": RecommendedActionType.SEND_NOTIFICATION, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.00},

    # 14% Unknown (7 cases)
    {"id": "syn_44", "customer_name": "Frodo Baggins", "amount": 550.0, "failure_code": "UNKNOWN_ERROR", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.20},
    {"id": "syn_45", "customer_name": "Samwise Gamgee", "amount": 120.0, "failure_code": "ERROR_500", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.60, "recovery_chance_retry": 0.20},
    {"id": "syn_46", "customer_name": "Aragorn King", "amount": 15000.0, "failure_code": "DO_NOT_HONOR", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.40, "recovery_chance_retry": 0.05},
    {"id": "syn_47", "customer_name": "Legolas Elf", "amount": 2500.0, "failure_code": "UNKNOWN_REASON", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "WHATSAPP", "recovery_chance_link": 0.55, "recovery_chance_retry": 0.15},
    {"id": "syn_48", "customer_name": "Gimli Dwarf", "amount": 950.0, "failure_code": "BLOCKED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.50, "recovery_chance_retry": 0.10},
    {"id": "syn_49", "customer_name": "Gandalf Grey", "amount": 25000.0, "failure_code": "SERVER_BLOCKED", "payment_type": PaymentType.RECURRING, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "SMS", "recovery_chance_link": 0.35, "recovery_chance_retry": 0.05},
    {"id": "syn_50", "customer_name": "Gollum Ring", "amount": 99.0, "failure_code": "UNKNOWN_ERROR", "payment_type": PaymentType.ONE_TIME, "expected_diagnosis": DiagnosisType.UNKNOWN, "expected_action": RecommendedActionType.CREATE_PAYMENT_LINK, "preferred_channel": "EMAIL", "recovery_chance_link": 0.70, "recovery_chance_retry": 0.30}
]

class EvaluationEngine:
    @staticmethod
    def run_baseline_recovery() -> MetricSummary:
        """
        Simulates the traditional baseline algorithm over the dataset.
        Strategy: Blindly retry after 24 hours, up to maximum 3 attempts.
        Cost parameters:
        - Retry fee: ₹50
        """
        random.seed(42)  # Fixed seed for reproducibility

        total_cases = len(SYNTHETIC_DATASET)
        total_at_risk_inr = sum(c["amount"] for c in SYNTHETIC_DATASET)
        
        recovered_cases = 0
        recovered_inr = 0.0
        total_attempts = 0
        total_time_hours = 0.0
        
        total_card_retries = 0
        false_positive_cost = 0.0
        
        for case in SYNTHETIC_DATASET:
            amount = case["amount"]
            retry_chance = case["recovery_chance_retry"]
            
            attempts_made = 0
            recovered = False
            time_taken = 0.0
            
            # Checkout abandonment has no card on file, retry is not possible (immediately fails/0 attempts)
            if case["expected_diagnosis"] == DiagnosisType.CHECKOUT_ABANDONMENT:
                attempts_made = 0
            else:
                for attempt in range(1, 4):  # max 3 attempts
                    attempts_made += 1
                    total_card_retries += 1
                    
                    # False-positive cost: retry was attempted, but expected action is NOT retry
                    if case["expected_action"] != RecommendedActionType.RETRY_PAYMENT:
                        false_positive_cost += 50.0

                    # Roll based on probability
                    if random.random() < retry_chance:
                        recovered = True
                        time_taken = attempt * 24.0
                        break
            
            total_attempts += attempts_made
            if recovered:
                recovered_cases += 1
                recovered_inr += amount
                total_time_hours += time_taken

        # Baseline unnecessary retry rate:
        # Retry is unnecessary if the card is expired or checkout is abandoned.
        unnecessary_retries = 0
        for case in SYNTHETIC_DATASET:
            if case["expected_diagnosis"] in {DiagnosisType.EXPIRED_PAYMENT_METHOD, DiagnosisType.CHECKOUT_ABANDONMENT}:
                if case["expected_diagnosis"] == DiagnosisType.EXPIRED_PAYMENT_METHOD:
                    unnecessary_retries += 3

        total_possible_actions = total_card_retries
        unnecessary_retry_rate = (unnecessary_retries / total_possible_actions) if total_possible_actions > 0 else 0.0
        
        operational_recovery_cost = total_card_retries * 50.0

        return MetricSummary(
            recovered_inr=recovered_inr,
            total_at_risk_inr=total_at_risk_inr,
            recovery_rate_inr=(recovered_inr / total_at_risk_inr) * 100.0,
            recovered_cases=recovered_cases,
            total_cases=total_cases,
            recovery_rate_count=(recovered_cases / total_cases) * 100.0,
            recovery_attempt_overhead=total_attempts / max(recovered_cases, 1),
            avg_attempts_per_case=total_attempts / total_cases,
            unnecessary_retry_rate=unnecessary_retry_rate * 100.0,
            operational_recovery_cost=operational_recovery_cost,
            false_positive_cost=false_positive_cost,
            avg_time_to_recovery_hours=total_time_hours / max(recovered_cases, 1),
            diagnosis_accuracy=0.0,  # Baseline has no AI diagnosis
            action_accuracy=0.0      # Baseline has no AI action selection
        )

    @classmethod
    def run_ai_recovery(cls, llm_key: str = None) -> tuple[MetricSummary, int]:
        """
        Simulates the AI Recovery Engine + Policy Engine over the dataset.
        For each case, it invokes LLMService.diagnose_and_recommend, checks Policy validation,
        and simulates the execution outcomes based on expected strategy recovery chance.
        """
        random.seed(42)  # Same seed for fair comparison
        
        from app.ai import LLMService
        
        total_cases = len(SYNTHETIC_DATASET)
        total_at_risk_inr = sum(c["amount"] for c in SYNTHETIC_DATASET)
        
        recovered_cases = 0
        recovered_inr = 0.0
        total_attempts = 0
        total_time_hours = 0.0
        
        correct_diagnoses = 0
        correct_actions = 0
        
        operational_recovery_cost = 0.0
        false_positive_cost = 0.0
        unnecessary_retries = 0
        total_card_retries = 0
        
        for case in SYNTHETIC_DATASET:
            amount = case["amount"]
            
            # Construct context
            payment_ctx = {
                "amount": amount,
                "currency": "INR",
                "failure_code": case["failure_code"]
            }
            customer_ctx = {
                "name": case["customer_name"],
                "preferred_channel": case["preferred_channel"]
            }
            
            # Invoke LLM (or fallback)
            # Simulate initial run (attempt = 0)
            decision = LLMService.diagnose_and_recommend(payment_ctx, customer_ctx, 0)
            
            # Evaluate Accuracy of AI layer against Independent Ground Truth
            if decision.diagnosis == case["expected_diagnosis"]:
                correct_diagnoses += 1
            if decision.recommended_action == case["expected_action"]:
                correct_actions += 1

            # Simulate recovery behavior:
            recovered = False
            attempts_made = 0
            time_taken = 0.0
            
            # AI recovery execution flow based on recommended strategy:
            strategy = decision.recommended_action
            delay = decision.delay_hours
            
            # False-positive check: If AI selection does not match expected strategy
            is_incorrect = strategy != case["expected_action"]
            
            # Determine outcome based on strategy
            if strategy == RecommendedActionType.RETRY_PAYMENT or strategy == RecommendedActionType.WAIT_AND_RETRY:
                # Direct card charge retry
                attempts_made += 1
                total_card_retries += 1
                operational_recovery_cost += 50.0  # Retry fee
                
                if is_incorrect:
                    false_positive_cost += 50.0
                
                # Check if unnecessary retry
                if case["expected_diagnosis"] in {DiagnosisType.EXPIRED_PAYMENT_METHOD, DiagnosisType.CHECKOUT_ABANDONMENT}:
                    unnecessary_retries += 1
                
                if random.random() < case["recovery_chance_retry"]:
                    recovered = True
                    time_taken = float(delay) + 1.0  # delay + execution window
                else:
                    # AI strategy fallback: if retry fails, policy engine/executor creates payment link as a fallback
                    # This adds a notification cost and secondary attempt
                    operational_recovery_cost += 5.0  # Notification cost
                    attempts_made += 1
                    if random.random() < case["recovery_chance_link"]:
                        recovered = True
                        time_taken = float(delay) + 25.0  # delay + 24h wait

            elif strategy == RecommendedActionType.CREATE_PAYMENT_LINK:
                # Send payment link notification
                attempts_made += 1
                operational_recovery_cost += 5.0  # Notification fee
                if is_incorrect:
                    false_positive_cost += 5.0
                
                if random.random() < case["recovery_chance_link"]:
                    recovered = True
                    time_taken = float(delay) + 4.0  # delay + response window (e.g. 4 hours average)
                    
            elif strategy == RecommendedActionType.SEND_NOTIFICATION:
                # Send notification (e.g. checkout abandonment)
                attempts_made += 1
                operational_recovery_cost += 5.0  # Notification fee
                if is_incorrect:
                    false_positive_cost += 5.0
                
                if random.random() < case["recovery_chance_link"]:
                    recovered = True
                    time_taken = float(delay) + 2.0  # delay + check window

            elif strategy == RecommendedActionType.ESCALATE:
                attempts_made += 1
                operational_recovery_cost += 500.0  # Heavy human escalation fee
                if is_incorrect:
                    false_positive_cost += 500.0
                
                # 30% recovery rate for collections team
                if random.random() < 0.30:
                    recovered = True
                    time_taken = 72.0  # 3 days

            total_attempts += attempts_made
            if recovered:
                recovered_cases += 1
                recovered_inr += amount
                total_time_hours += time_taken

        unnecessary_retry_rate = (unnecessary_retries / total_card_retries) if total_card_retries > 0 else 0.0

        metrics = MetricSummary(
            recovered_inr=recovered_inr,
            total_at_risk_inr=total_at_risk_inr,
            recovery_rate_inr=(recovered_inr / total_at_risk_inr) * 100.0,
            recovered_cases=recovered_cases,
            total_cases=total_cases,
            recovery_rate_count=(recovered_cases / total_cases) * 100.0,
            recovery_attempt_overhead=total_attempts / max(recovered_cases, 1),
            avg_attempts_per_case=total_attempts / total_cases,
            unnecessary_retry_rate=unnecessary_retry_rate * 100.0,
            operational_recovery_cost=operational_recovery_cost,
            false_positive_cost=false_positive_cost,
            avg_time_to_recovery_hours=total_time_hours / max(recovered_cases, 1),
            diagnosis_accuracy=(correct_diagnoses / total_cases) * 100.0,
            action_accuracy=(correct_actions / total_cases) * 100.0
        )

        return metrics, total_cases

    @classmethod
    def run_evaluation(cls) -> EvaluationResults:
        """
        Runs both the baseline and AI-driven simulators and outputs results.
        """
        from app.config import settings
        baseline_metrics = cls.run_baseline_recovery()
        ai_metrics, cases_run = cls.run_ai_recovery()
        
        execution_mode = "LIVE LLM MODE · Gemini" if settings.LLM_API_KEY else "OFFLINE MODE · Deterministic Fallback"
        
        return EvaluationResults(
            baseline=baseline_metrics,
            ai_recovery=ai_metrics,
            cases_run=cases_run,
            dataset_size=50,
            random_seed=42,
            execution_mode=execution_mode
        )
