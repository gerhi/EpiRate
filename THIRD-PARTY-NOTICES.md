# Third-Party Notices

Dieses Projekt nutzt die folgenden Open-Source-Bibliotheken und Modelle.
Die jeweiligen Lizenzen gelten für die entsprechenden Komponenten.

## Python-Bibliotheken (via pip)

| Paket           | Version | Lizenz     | Quelle                                              |
|-----------------|---------|------------|------------------------------------------------------|
| Flask           | 3.0.0   | BSD-3      | https://github.com/pallets/flask                     |
| Werkzeug        | 3.0.1   | BSD-3      | https://github.com/pallets/werkzeug                  |
| PyMySQL         | 1.1.0   | MIT        | https://github.com/PyMySQL/PyMySQL                   |
| qrcode          | 7.4.2   | BSD        | https://github.com/lincolnloop/python-qrcode         |
| Pillow          | 10.1.0  | HPND       | https://github.com/python-pillow/Pillow              |
| torch (PyTorch) | 2.1.0   | BSD-3      | https://github.com/pytorch/pytorch                   |
| transformers    | 4.35.0  | Apache-2.0 | https://github.com/huggingface/transformers          |
| pandas          | 2.1.3   | BSD-3      | https://github.com/pandas-dev/pandas                 |
| openpyxl        | 3.1.2   | MIT        | https://github.com/theorchard/openpyxl               |
| ReportLab       | 4.0.7   | BSD        | https://github.com/MReporter/reportlab               |
| python-dotenv   | 1.0.0   | BSD-3      | https://github.com/theskumar/python-dotenv           |

## ML-Modelle (zur Laufzeit heruntergeladen)

### piiranha-v1-detect-personal-information

- **Autor:** iiiorg
- **Lizenz:** CC-BY-NC-ND-4.0 (Creative Commons Attribution-NonCommercial-NoDerivatives 4.0)
- **Quelle:** https://huggingface.co/iiiorg/piiranha-v1-detect-personal-information
- **Basiert auf:** microsoft/mdeberta-v3-base (MIT-Lizenz)

> **WICHTIG:** Die CC-BY-NC-ND-4.0-Lizenz des piiranha-Modells erlaubt
> **keine kommerzielle Nutzung** und **keine Bearbeitungen/Ableitungen**
> des Modells. Dies betrifft nicht den EpiRate-Quellcode selbst (MIT-Lizenz),
> sondern ausschließlich das zur Laufzeit geladene ML-Modell. Nutzer, die
> EpiRate kommerziell einsetzen möchten, müssen entweder eine gesonderte
> Lizenz für das piiranha-Modell einholen oder ein alternatives PII-Modell
> mit kompatibler Lizenz verwenden.

### microsoft/mdeberta-v3-base (Basismodell von piiranha)

- **Autor:** Microsoft
- **Lizenz:** MIT
- **Quelle:** https://huggingface.co/microsoft/mdeberta-v3-base

## Frontend-Bibliotheken

| Bibliothek | Lizenz | Quelle                              |
|------------|--------|--------------------------------------|
| Bootstrap  | MIT    | https://github.com/twbs/bootstrap    |
| jQuery     | MIT    | https://github.com/jquery/jquery     |
| Select2    | MIT    | https://github.com/select2/select2   |
