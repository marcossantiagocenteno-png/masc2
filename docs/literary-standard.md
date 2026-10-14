# Criterio literario de Novel Engine

Este documento define qué significa "buena calidad" para el benchmark en su versión inicial. Es un criterio de trabajo, no una verdad establecida. Cambiará cuando haya evaluaciones reales que lo contrasten.

Etiquetas de confianza usadas en este documento:

- **[Cierto]**: principio ampliamente respaldado por la práctica editorial o por hechos verificables.
- **[Probable]**: criterio profesional razonable, discutible en casos concretos.
- **[Suposición]**: decisión de diseño tomada porque falta información. Debe revisarse con el autor.

## 1. Prioridades

Al evaluar un texto, el orden de prioridad es:

1. Dramaturgia: que cada escena cambie algo y que los cambios tengan causa. [Probable]
2. Personajes y diálogo: que los personajes decidan y que el diálogo tenga intención. [Probable]
3. Focalización: que la información llegue al lector a través de lo que el punto de vista puede saber. [Cierto]
4. Continuidad: que hechos básicos no se contradigan. [Cierto]
5. Prosa y voz: que cada frase diga lo que debe decir y suene a su narrador. [Probable]

La prosa va en último lugar, no porque sea irrelevante, sino porque una frase bien escrita no salva una escena sin conflicto. [Probable]

## 2. Gusto y oficio

El benchmark distingue dos tipos de juicio.

- **Oficio**: un problema que genera un efecto narrativo concreto. Ejemplo: "el narrador revela la causa de la muerte antes de que el personaje la descubra, y la investigación pierde sentido". Puede ser un defecto crítico.
- **Gusto**: una preferencia personal que no produce un problema narrativo demostrable. Ejemplo: "preferiría frases más cortas". No penaliza la puntuación.

La rúbrica recoge ambos en listas separadas. Los defectos críticos son de oficio. Las preferencias estilísticas son de gusto y no pueden bajar la puntuación. [Probable]

## 3. Qué es un defecto crítico

Un defecto es crítico cuando cumple al menos una de estas condiciones:

- Impide entender qué ocurre en la escena.
- Rompe una regla que el propio texto ha establecido (edad, lugar, pista, estado de un objeto).
- Revela información que el punto de vista no puede conocer, sin justificación.
- Elimina la tensión de una escena sin que ningún personaje tome una decisión.
- Resuelve un conflicto principal con una coincidencia no preparada.

Un texto con defectos críticos no puede puntuar más de 2 en la dimensión afectada. Esta regla está implementada en `DimensionScore` (ver `decisions.md`).

## 4. Escena

Una escena se evalúa por lo que cambia. La pregunta mínima es: ¿quién entra queriendo algo, qué le impide conseguirlo y qué queda diferente al salir? [Probable]

Una escena puede sostenerse con tensión psicológica, información, secreto o silencio. No es obligatorio un conflicto externo. Lo que no puede faltar es una razón narrativa para que la escena exista. [Probable]

## 5. Diálogo

El diálogo debe tener intención: obtener algo, evitar algo, ocultar algo o imponerse. No debe transmitir al lector información que los dos personajes ya conocen. [Cierto]

## 6. Focalización

Si el relato está filtrado por un personaje, el narrador solo puede mostrar lo que ese personaje pudo observar, oír o deducir. La distancia narrativa es válida si es deliberada y no revela información antes de tiempo. [Cierto]

## 7. Continuidad

Edades, fechas, lugares, relaciones, objetos clave y conocimientos de cada personaje deben ser coherentes a lo largo del texto. Una contradicción solo se acepta si el texto la explica. [Cierto]

## 8. Prosa y voz

La prosa se evalúa en este orden: que la frase diga exactamente lo que debe decir, que suene al narrador, que tenga ritmo y, por último, que sea precisa. La belleza no se evalúa por sí sola. [Probable]

Una metáfora solo cuenta a favor si nace de la percepción del personaje. La ornamentación que no añade información se considera un defecto de oficio cuando produce ambigüedad, y una preferencia de gusto en los demás casos. [Probable]

## 9. Lo que el benchmark no puede afirmar

- No mide si un texto es literariamente bueno. Solo comprueba que los casos y las evaluaciones tienen la forma correcta.
- Ninguna puntuación de los casos de ejemplo es una calificación real. Los casos son ilustrativos y ficticios.
- La rúbrica v1 no ha sido calibrada con evaluadores humanos. Sus descriptores son una propuesta que debe contrastarse.

El benchmark solo podrá afirmar algo sobre calidad después de ejecutar evaluaciones reales y de comparar sus resultados con juicios de lectores cualificados.

## 10. Preguntas abiertas para el autor

- ¿Qué tipos de novela deben medirse primero? [Suposición: el benchmark asume narrativa de ficción en español.]
- ¿Qué pesos tienen las dimensiones al combinarlas? La fase 0 no combina puntuaciones.
- ¿Quién puntúa: un revisor humano, un modelo o ambos? Pendiente.
