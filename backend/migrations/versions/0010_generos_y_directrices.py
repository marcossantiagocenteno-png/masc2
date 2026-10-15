"""Géneros seleccionables y directrices narrativas (F1 de la construcción progresiva).

Revisión: 0010_generos_y_directrices
Revisión anterior: 0009_escritura_escenas

Cambio aditivo:
- ``project_genres``: géneros seleccionados por proyecto. Se crea y se rellena desde ``projects.genre``
  (texto libre). Un valor que coincide con una clave o una etiqueta del catálogo pasa a esa clave; cualquier
  otro se conserva como ``otro`` con su texto exacto.
- ``narrative_directives``: directrices narrativas, una fila por proyecto.

No se modifica ``projects``: ``genre``, ``synopsis``, ``tone`` y ``premise`` conservan sus valores.
La bajada no es automática.
"""

from __future__ import annotations

import unicodedata

import sqlalchemy as sa
from alembic import op

revision: str = "0010_generos_y_directrices"
down_revision: str | None = "0009_escritura_escenas"
branch_labels = None
depends_on = None

# Copia congelada del catálogo de la versión 0010: una migración no debe cambiar si el catálogo cambia después.
_CATALOGO = {
    "misterio": "Misterio e investigación",
    "thriller": "Thriller y suspense",
    "romance": "Romance",
    "terror": "Terror",
    "aventura": "Aventura",
    "formacion": "Novela de formación",
    "tragedia": "Tragedia",
    "fantasia": "Fantasía",
    "ciencia_ficcion": "Ciencia ficción",
    "historica": "Novela histórica",
    "realismo": "Realismo",
    "drama": "Drama",
    "humor": "Humor",
}


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


def _clave_de(texto: str) -> str | None:
    """Clave del catálogo para un texto libre, solo si coincide exactamente con una clave o una etiqueta."""
    objetivo = _normalizar(texto)
    for clave, etiqueta in _CATALOGO.items():
        if objetivo in (_normalizar(clave), _normalizar(etiqueta)):
            return clave
    return None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError(f"Esta migración solo está probada para SQLite; dialecto: {bind.dialect.name}")

    op.create_table(
        "project_genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("genre_key", sa.String(40), nullable=False),
        sa.Column("custom_label", sa.String(120), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "genre_key", "custom_label", name="uq_project_genres"),
    )
    op.create_index("ix_project_genres_project_id", "project_genres", ["project_id"])

    op.create_table(
        "narrative_directives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("voz", sa.String(200), nullable=True),
        sa.Column("persona", sa.String(20), nullable=True),
        sa.Column("tiempo_verbal", sa.String(20), nullable=True),
        sa.Column("tipo_narrador", sa.String(40), nullable=True),
        sa.Column("punto_de_vista", sa.String(40), nullable=True),
        sa.Column("focalizacion", sa.String(40), nullable=True),
        sa.Column("estilo", sa.Text(), nullable=True),
        sa.Column("intencion", sa.Text(), nullable=True),
        sa.Column("limites", sa.Text(), nullable=True),
        sa.Column("instrucciones", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_narrative_directives_project"),
    )
    op.create_index("ix_narrative_directives_project_id", "narrative_directives", ["project_id"])

    # Relleno desde el texto existente. Solo inserta; no toca projects.
    filas = bind.execute(
        sa.text("SELECT id, genre, created_at FROM projects WHERE genre IS NOT NULL AND TRIM(genre) <> ''")
    ).fetchall()
    for proyecto_id, texto, creado in filas:
        clave = _clave_de(texto)
        etiqueta = None if clave else texto.strip()[:120]
        bind.execute(
            sa.text(
                "INSERT INTO project_genres (project_id, genre_key, custom_label, activo, created_at) "
                "VALUES (:p, :k, :l, 1, :c)"
            ),
            {"p": proyecto_id, "k": clave or "otro", "l": etiqueta, "c": creado},
        )


def downgrade() -> None:
    raise NotImplementedError("La bajada de 0010 no es automática. Restaura la copia anterior a esta migración.")
