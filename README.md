# 📊 Enterprise Data Warehouse & Analytics Platform (EAF & FIMSS 2025)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![DuckDB](https://img.shields.io/badge/DuckDB-OLAP-yellow)
![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-red)
![Architecture](https://img.shields.io/badge/Architecture-Star--Schema-green)

## 📌 Executive Summary
This repository contains an end-to-end Modern Data Stack (MDS) implementation for unifying, transforming, and analyzing heterogeneous registration datasets across major corporate and public events (**EAF 2025** and **FIMSS 2025**).

The architecture ingests raw records, performs automated normalization, deduplicates participant profiles, and enforces a Star Schema representation hosted on a high-performance **DuckDB** analytical engine.

---

## 🏗️ Data Architecture & Modeling

The Data Warehouse is structured using a Dimensional Star Schema:

* **Fact Table (`fact_inscripciones`)**: Consolidates 6,943 transaction records including pricing tier, distance, category, registration method, and timestamp.
* **Dimension Tables**:
  * `dim_eventos`: Event metadata (`EAF 2025`, `FIMSS 2025`).
  * `dim_participantes`: Entity collection of 6,924 unique deduplicated participant profiles.
  * `dim_operadoras`: Organizational channels and corporate entities.
  * `dim_cupones`: Promotional codes and discount tracking.

---

## 🚀 Technical Stack

* **Storage & Analytics**: DuckDB (In-process SQL OLAP engine).
* **ETL Pipeline**: Python (`pandas`, `openpyxl`) for data cleaning, column standardization, and schema mapping.
* **Visualization Layer**: Streamlit Cloud + Plotly for real-time interactive business intelligence.
