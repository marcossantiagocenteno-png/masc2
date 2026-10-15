/**
 * Rutas de manuscritos y versiones. Un manuscrito con proyecto vive dentro de su novela; uno sin proyecto
 * sigue en /manuscritos. Los identificadores llegan del servidor, nunca de la URL.
 */
export function manuscriptPath(projectId: number | null, manuscriptId: number): string {
  return projectId === null ? `/manuscritos/${manuscriptId}` : `/proyectos/${projectId}/manuscritos/${manuscriptId}`;
}

export function versionPath(projectId: number | null, manuscriptId: number, versionId: number): string {
  return `${manuscriptPath(projectId, manuscriptId)}/versiones/${versionId}`;
}
