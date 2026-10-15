/**
 * Eventos del espacio de trabajo. Un análisis guardado se anuncia para que la columna de contexto vuelva a leer
 * los análisis de la versión. El evento no lleva datos: quien escucha vuelve a pedirlos a la API.
 */
export const ANALISIS_GUARDADO = "novel-engine:analisis-guardado";

export function anunciarAnalisisGuardado() {
  window.dispatchEvent(new Event(ANALISIS_GUARDADO));
}
