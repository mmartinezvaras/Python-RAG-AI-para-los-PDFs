# Evaluation results

Generated on 2026-11-08 by `python -m eval.run_eval`. LLM `llama3.2:3b`, embeddings `nomic-embed-text`, judge `llama3.2:3b`, chunks 1000/150, top-k 5, relevance gate 0.64.

| Metric | hybrid | vector |
|---|---|---|
| Retrieval hit@k | 87% | 80% |
| MRR@k | 0.73 | 0.69 |
| Answer accuracy | 77% | 70% |
| Correct “not in the documents” | 100% | 100% |
| Answerable questions blocked by the gate | 0 | 0 |
| Median time per answer | 44.0 s | 37.0 s |

**Relevance gate calibration** (best cosine similarity per question): answerable min 0.68 / median 0.74; not answerable median 0.66 / max 0.70. A good threshold sits between the two.

## Misses

| Mode | Question | Article found | Answer |
|---|---|---|---|
| hybrid | ¿Cuánto dura como mínimo el descanso semanal? | yes | El descanso semanal dura como mínimo dos días ininterrumpidos. [1] |
| hybrid | ¿A partir de qué edad se puede trabajar? | no | No se menciona la edad mínima para trabajar en los pasajes proporcionados. |
| hybrid | ¿Pueden los menores de 18 años hacer horas extraordinarias? | yes | Sí, los menores de 18 años pueden realizar horas extraordinarias, pero solo si se han pactado en convenio colectivo o contrato individual de trabajo, y siempre  |
| hybrid | ¿Qué indemnización corresponde por un despido por causas objetivas? | yes | La indemnización corresponde a treinta y tres días de salario por año de servicio, prorrateándose por meses los periodos de tiempo inferiores a un año, hasta un |
| hybrid | ¿Qué plazo hay para reclamar contra un despido? | no | El plazo para reclamar contra un despido es dentro del día laborable siguiente a la proclamación del acuerdo de despido. [1] |
| hybrid | ¿Con cuánta antelación debe avisar el empresario de la finalización de un contrato temporal de más de un año? | no | No se menciona en las pasadas la cantidad de antelación en las que el empresario debe avisar de la finalización de un contrato temporal de más de un año. |
| hybrid | How long can the probation period be for qualified technicians? | no | The documents don't include that information. |
| vector | ¿Cuántas horas ordinarias de trabajo efectivo se pueden hacer como máximo al día? | no | Se pueden hacer como máximo 8 horas ordinarias de trabajo efectivo al día. [1] |
| vector | ¿Qué porcentaje de la jornada anual puede distribuir la empresa de forma irregular? | yes | El documento no establece un porcentaje específico de la jornada anual que puede distribuir la empresa de forma irregular. |
| vector | ¿Hasta qué edad del hijo se puede pedir una reducción de jornada por guarda legal? | yes | No se menciona en los pasajes proporcionados la edad específica hasta la que se puede pedir una reducción de jornada por guarda legal. |
| vector | ¿A partir de qué edad se puede trabajar? | no | No se menciona la edad mínima para trabajar en los pasajes proporcionados. |
| vector | ¿Qué indemnización corresponde por un despido por causas objetivas? | yes | La indemnización correspondiente a un despido por causas objetivas es equivalente a treinta y tres días de salario por año de servicio, prorrateándose por meses |
| vector | ¿Qué plazo hay para reclamar contra un despido? | no | El plazo para reclamar contra un despido es dentro del día laborable siguiente a la proclamación del acuerdo de despido. |
| vector | ¿Con cuánta antelación debe avisar el empresario de la finalización de un contrato temporal de más de un año? | no | No se menciona en las pasadas la cantidad de antelación en las que el empresario debe avisar de la finalización de un contrato temporal de más de un año. |
| vector | What is the maximum length of the ordinary working week? | no | The documents don't include that information. |
| vector | How long can the probation period be for qualified technicians? | no | The documents don't include that information. |
