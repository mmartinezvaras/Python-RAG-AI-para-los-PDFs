# Evaluation results

Generated on 2026-11-08 by `python -m eval.run_eval`. LLM `llama3.2:3b`, embeddings `nomic-embed-text`, judge `llama3.2:3b`, chunks 1000/150, top-k 5, relevance gate 0.64.

| Metric | hybrid | vector |
|---|---|---|
| Retrieval hit@k | 87% | 80% |
| MRR@k | 0.73 | 0.69 |
| Answer accuracy | 73% | 60% |
| Correct “not in the documents” | 100% | 100% |
| Answerable questions blocked by the gate | 0 | 0 |
| Median time per answer | 27.9 s | 21.8 s |

**Relevance gate calibration** (best cosine similarity per question): answerable min 0.68 / median 0.74; not answerable median 0.66 / max 0.70. A good threshold sits between the two.

## Misses

| Mode | Question | Article found | Answer |
|---|---|---|---|
| hybrid | ¿Hasta qué edad del hijo se puede pedir una reducción de jornada por guarda legal? | yes | Se puede pedir una reducción de jornada hasta que el causante cumpla 26 años si antes de alcanzar los 23 años acredita un grado de discapacidad igual o superior |
| hybrid | ¿A partir de qué edad se puede trabajar? | no | No se menciona la edad mínima para trabajar en los pasajes proporcionados. |
| hybrid | ¿Qué indemnización corresponde por un despido por causas objetivas? | yes | La indemnización corresponde por un despido por causas objetivas, siempre y cuando se acredite la extinción del contrato de la persona referida. [1] |
| hybrid | ¿Qué plazo hay para reclamar contra un despido? | no | Se puede reclamar dentro del día laborable siguiente, resolviendo la mesa en el posterior día hábil, contra el acuerdo de proclamación del despido. [1] |
| hybrid | ¿Con cuánta antelación debe avisar el empresario de la finalización de un contrato temporal de más de un año? | no | No se menciona en las pasadas la cantidad de antelación en las que el empresario debe avisar de la finalización de un contrato temporal de más de un año. |
| hybrid | How many days of paid annual leave does a worker get? | yes | El trabajador obtiene al menos treinta días naturales de vacaciones pagadas anuales. [1] |
| hybrid | How long can the probation period be for qualified technicians? | no | No se menciona en los pasajes proporcionados la duración del período de probación para técnicos calificados. |
| hybrid | What severance pay applies to an unfair dismissal? | yes | El pago de despido que se aplica a una despistación injusta es una indemnización equivalente a treinta y tres días de salario por año de servicio, prorrateándos |
| vector | ¿Cuántas horas ordinarias de trabajo efectivo se pueden hacer como máximo al día? | no | Se pueden hacer como máximo 8 horas ordinarias de trabajo efectivo al día. [1] |
| vector | ¿Qué porcentaje de la jornada anual puede distribuir la empresa de forma irregular? | yes | El documento no establece un porcentaje específico de la jornada anual que puede distribuir la empresa de forma irregular. |
| vector | ¿Hasta qué edad del hijo se puede pedir una reducción de jornada por guarda legal? | yes | No se menciona en los pasajes proporcionados la edad específica hasta la que se puede pedir una reducción de jornada por guarda legal. |
| vector | ¿A partir de qué edad se puede trabajar? | no | No se menciona la edad mínima para trabajar en los pasajes proporcionados. |
| vector | ¿Qué indemnización corresponde por un despido por causas objetivas? | yes | La indemnización corresponde a treinta y tres días de salario por año de servicio, prorrateándose por meses los periodos de tiempo inferiores a un año, hasta un |
| vector | ¿Qué plazo hay para reclamar contra un despido? | no | Se puede reclamar dentro del día laborable siguiente, resolviendo la mesa en el posterior día hábil, contra el acuerdo de proclamación del despido. [1] |
| vector | ¿Con cuánta antelación debe avisar el empresario de la finalización de un contrato temporal de más de un año? | no | No se menciona en las pasadas la cantidad de antelación en las que el empresario debe avisar de la finalización de un contrato temporal de más de un año. |
| vector | ¿Qué antigüedad se necesita para pedir una excedencia voluntaria y cuánto puede durar? | yes | Para pedir una excedencia voluntaria, el trabajador necesita al menos una antigüedad de una año en la empresa. La duración de la excedencia voluntaria no puede  |
| vector | How many days of paid annual leave does a worker get? | yes | Un trabajador obtiene al menos treinta días naturales de vacaciones pagadas anuales. [1] |
| vector | What is the maximum length of the ordinary working week? | no | La longitud máxima de la semana laboral ordinaria no está especificada en los pasajes proporcionados. |
| vector | How long can the probation period be for qualified technicians? | no | No se menciona en los pasajes proporcionados cómo puede durar el período de probación para técnicos calificados. |
| vector | What severance pay applies to an unfair dismissal? | yes | El pago de despido que se aplica a una despistación injusta es una indemnización equivalente a treinta y tres días de salario por año de servicio, prorrateándos |
