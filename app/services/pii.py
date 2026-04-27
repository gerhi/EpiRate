"""PII-Erkennung (personenbezogene Daten) mittels NER-Modell.

Lazy Loading: torch + transformers werden erst beim ersten Aufruf importiert,
um die Startzeit der App nicht zu belasten (~2–5s Ladezeit beim ersten Request).
"""

_model = None
_tokenizer = None
_device = None


def _load_model():
    """Lädt das Piiranha-NER-Modell einmalig (Singleton)."""
    global _model, _tokenizer, _device
    if _model is None:
        import torch
        from transformers import AutoTokenizer, AutoModelForTokenClassification

        model_name = "iiiorg/piiranha-v1-detect-personal-information"
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForTokenClassification.from_pretrained(model_name)
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _model.to(_device)
    return _model, _tokenizer, _device


def _apply_redaction(masked_text, start, end, pii_type, aggregate_redaction):
    for j in range(start, end):
        masked_text[j] = ""
    if aggregate_redaction:
        masked_text[start] = " [redacted]"
    else:
        masked_text[start] = f"[{pii_type}]"


def mask_pii(text, aggregate_redaction=False):
    """Ersetzt erkannte PII im Text durch [Typ]-Platzhalter. Gibt (maskierter_text, wahrscheinlichkeiten) zurück."""
    import torch
    import torch.nn.functional as F

    model, tokenizer, device = _load_model()

    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    probabilities = F.softmax(logits, dim=-1)
    predictions = torch.argmax(logits, dim=-1)

    encoded_inputs = tokenizer.encode_plus(text, return_offsets_mapping=True, add_special_tokens=True, truncation=True, max_length=512)
    offset_mapping = encoded_inputs["offset_mapping"]

    masked_text = list(text)
    pii_probabilities = {}
    is_redacting = False
    redaction_start = 0
    current_pii_type = ""

    for i, (start, end) in enumerate(offset_mapping):
        if start == end:
            continue

        label = predictions[0][i].item()
        prob = probabilities[0][i][label].item()
        pii_type = model.config.id2label[label]

        # Schwellenwert 0.85: Balance zwischen Erkennung und False Positives; USERNAME ignorieren
        if label != model.config.label2id["O"] and prob > 0.85 and "USERNAME" not in pii_type:
            if not is_redacting:
                is_redacting = True
                redaction_start = start
                current_pii_type = pii_type
            elif not aggregate_redaction and pii_type != current_pii_type:
                _apply_redaction(masked_text, redaction_start, start, current_pii_type, aggregate_redaction)
                pii_probabilities[f"{current_pii_type}_{redaction_start}"] = prob
                redaction_start = start
                current_pii_type = pii_type
        else:
            if is_redacting:
                _apply_redaction(masked_text, redaction_start, end, current_pii_type, aggregate_redaction)
                pii_probabilities[f"{current_pii_type}_{redaction_start}"] = prob
                is_redacting = False

    if is_redacting:
        _apply_redaction(masked_text, redaction_start, len(masked_text), current_pii_type, aggregate_redaction)
        pii_probabilities[f"{current_pii_type}_{redaction_start}"] = prob

    return "".join(masked_text), pii_probabilities


PII_FRIENDLY_NAMES = {
    "I-ACCOUNTNUM": "account number",
    "I-BUILDINGNUM": "building number",
    "I-CITY": "city name",
    "I-CREDITCARDNUMBER": "credit card number",
    "I-DATEOFBIRTH": "date of birth",
    "I-DRIVERLICENSENUM": "driver's license number",
    "I-EMAIL": "email address",
    "I-GIVENNAME": "first name",
    "I-IDCARDNUM": "ID card number",
    "I-PASSWORD": "password",
    "I-SOCIALNUM": "social security number",
    "I-STREET": "street name",
    "I-SURNAME": "last name",
    "I-TAXNUM": "tax identification number",
    "I-TELEPHONENUM": "phone number",
    "I-USERNAME": "username",
    "I-ZIPCODE": "zip code",
}


def get_friendly_pii_name(pii_type):
    return PII_FRIENDLY_NAMES.get(pii_type, pii_type.lower())
