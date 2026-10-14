import Link from "next/link";

/** Página inicial: estado del proyecto y acceso a manuscritos. */
const pendientes = [
  "Editor de manuscritos con Tiptap",
  "Generador de novelas y agentes autónomos",
  "Evaluación literaria con la rúbrica v1",
];

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-16 sm:px-6">
      <header className="flex flex-col gap-3">
        <p className="ne-kicker">
          Fase 0 · Fundamentos
        </p>
        <h1 className="ne-page-title ne-page-title--hero">Novel Engine</h1>
        <p className="ne-lede">
          Entorno privado de escritura y edición literaria asistida por IA.
          Esta fase establece la estructura, la rúbrica y el benchmark inicial.
        </p>
        <p className="flex gap-4">
          <Link href="/proyectos" className="ne-link font-medium">
            Proyectos
          </Link>
          <Link href="/manuscritos" className="ne-link font-medium">
            Manuscritos sueltos
          </Link>
        </p>
      </header>

      <section aria-labelledby="pendientes-titulo" className="flex flex-col gap-3">
        <h2 id="pendientes-titulo" className="ne-section-title">
          Pendiente para fases siguientes
        </h2>
        <ul className="list-disc space-y-1 pl-6">
          {pendientes.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
