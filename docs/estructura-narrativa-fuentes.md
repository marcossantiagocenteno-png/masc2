# Estructura narrativa: fuentes y evaluación de la premisa

Documento de referencia de la recomendación de estructura (F2). Explica qué afirma el catálogo, de dónde sale y qué
no está verificado. El código lo recoge en `backend/app/planning/recomendaciones.py` y
`backend/app/planning/premisa.py`.

## Principio

Las recomendaciones son orientación, no verdades literarias. Ningún modelo es obligatorio. Cada motivo del ranking
indica si es un dato del autor, una inferencia de una regla o una convención del género que puede ignorarse.
Nada de lo que aquí se calcula se guarda como canon.

## Modelos del catálogo

### 1. Pirámide de Freytag (cinco actos)

- **Origen:** Gustav Freytag, *Die Technik des Dramas* (1863). Modelo de cinco partes de la acción dramática.
- **Estado de la verificación:** las cinco partes están confirmadas por fuentes secundarias académicas. El texto
  original no se ha consultado.
- **Fuentes consultadas:**
  - Utrecht Dramaturgy Database, registro de *Die Technik des Dramas*:
    https://dramaturgydatabase.hum.uu.nl/record/die-technik-des-dramas/
  - Five-act model, wiki de narratología: https://tecfalabs.unige.ch/mediawiki-narrative/index.php/Five-act_model
- **Matiz:** algunas fuentes atribuyen a Freytag un esquema de juego y contrajuego con el clímax como punto de
  encuentro. Es una lectura menos común; el catálogo usa la versión de cinco partes.

### 2. Siete puntos (Dan Wells)

- **Origen:** Dan Wells lo presenta en el episodio 21.24 de *Writing Excuses*, «Deconstructing the Seven Point Plot
  Structure».
- **Estado de la verificación:** la presentación de Wells está confirmada por el propio programa. Las etapas (gancho,
  primer punto de giro, primera presión, punto medio, segunda presión, segundo punto de giro, resolución) coinciden
  en las guías secundarias consultadas. No se ha consultado la transcripción completa.
- **Fuentes consultadas:**
  - Writing Excuses 21.24: https://writingexcuses.com/21-24-deconstructing-the-seven-point-plot-structure/
  - Guías secundarias, usadas solo para contrastar nombres: https://www.tckpublishing.com/seven-point-story-structure/
- **Matiz:** las guías dan porcentajes aproximados (primer punto de giro cerca del 25 %, punto medio cerca del 50 %).
  El catálogo no los usa.

### 3. Save the Cat! (15 escenas)

- **Origen:** Blake Snyder, *Save the Cat!* (2005), método para planificar guiones de cine con 15 beats y páginas
  orientativas. Es un método de guion, no una teoría general de la estructura dramática.
- **Adaptación posterior:** Jessica Brody, *Save the Cat! Writes a Novel*. Adapta el método a la novela con otros
  porcentajes y listas de beats por género. **No es el método original.** El catálogo recoge la versión de Snyder.
- **Estado de la verificación:** los 15 beats y su orden coinciden con las fuentes consultadas. Las páginas exactas
  no se han contrastado con el libro, y las fuentes dan cifras distintas entre sí. El catálogo no usa páginas ni
  porcentajes.
- **Fuentes consultadas:**
  - Blake Snyder, entrada de Wikipedia: https://en.wikipedia.org/wiki/Blake_Snyder
  - MovieMaker, reseña del libro: https://www.moviemaker.com/first-draft-screenwriting-books/13/
  - Editor World, guía del beat sheet: https://www.editorworld.com/article/save-the-cat-beat-sheet
  - Random House, ficha de *Save the Cat! Writes a Novel*: https://www.randomhousebooks.com/books/554039

## Evaluación de la premisa

`premisa.py` no interpreta el sentido del texto. Busca pistas léxicas visibles y las separa en tres clases:

- **Hechos (confirmado):** lo que el autor escribió y decidió: el texto, el número de frases, los géneros y las
  directrices.
- **Inferencias:** cada pista muestra la palabra y la frase que la originaron, con confianza baja. `canon` es siempre
  falso.
- **Preguntas pendientes:** lo que la premisa no muestra.

Un léxico simple falla con ironía, negación y sentido figurado. Por eso cada pista es visible y el autor puede
contradecirla.

### Cómo afecta al ranking

Cada regla de premisa cita el criterio «favorece» de su propio modelo:

| Pista de la premisa | Criterio citado | Modelo afectado |
| --- | --- | --- |
| objetivo | un protagonista con un objetivo claro | Siete puntos (+1) |
| obstáculo con presión de tiempo | un conflicto central que se intensifica | Freytag (+1) |
| cambio del protagonista | un protagonista que cambia | Save the Cat! (+1) |

Cada modelo también recibe una limitación cuando la premisa no muestra lo que necesita.

### Confianza

- **insuficiente:** ningún dato apunta a ningún modelo.
- **baja:** hay datos, pero el primero apenas supera al segundo.
- **moderada:** el primero supera al segundo por dos o más puntos y la premisa cubre al menos dos categorías.

Nunca se muestra «alta». Mientras la confianza no sea moderada, la recomendación se presenta como provisional.

### Etapas ancladas a la premisa

Cada etapa se relaciona con los elementos de la premisa que le corresponden. Si la premisa contiene esa pista, la
pregunta cita la frase exacta. Si no, la pregunta queda como decisión del autor. Las funciones de las etapas son
genéricas: nunca se asignan acontecimientos.
