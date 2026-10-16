DATADEV AI — CURRENT PROJECT
============================

Main local language model: datadev_gpt_v5.py
Current checkpoint: datadev_gpt_v5_model.pt
Current vocabulary: datadev_gpt_v5_vocab.json

Main launchers
--------------
- DataDev GPT v5.bat: chat with the local v5 model
- DataDev GPT v5 - Egit.bat: train the v5 model
- DataDev AI - Groq Döngüsü.bat: local draft + Groq feedback loop
- DataDev AI - Gece Eğitimi.bat: overnight data collection/training workflow
- DataDev AI API.bat: local API, using the v5 model
- DataDev AI Groq Paneli.bat: training/approval control panel
- DataDev AI - Sabah Benchmark.bat: run the benchmark suite
- DataDev Hive - VDS Kur.bat / DataDev Hive - Worker.bat: distributed knowledge-bank workers

Important data — keep these
---------------------------
- datadev_master_dataset.jsonl and other *.jsonl training/evaluation records
- datadev_benchmark_questions.jsonl and benchmark reports
- datadev_interaction_training.jsonl and review/worker candidate data
- makaleler/ and kitaplar/ source material
- datadev_gpt_v5_train.log, datadev_gpt_v5_loss_grafik.svg, and training state/logs
- .env files and API-key files are local secrets/configuration; never publish them

The API, overnight trainer, Groq panel, loop and benchmark are configured to use v5.
DataDev Hive coordinates worker processing and maintains its own hive_data directory;
this is a knowledge/data workflow, not distributed gradient training.

Python syntax smoke check:
  python -m py_compile datadev_api.py datadev_gpt_v5.py datadev_gece_egitimi.py datadev_gpt_loop.py datadev_benchmark.py datadev_hive.py datadev_hive_sync.py