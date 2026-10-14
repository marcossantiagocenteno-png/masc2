/** Página inicial de la fase 0: solo describe el estado del proyecto. */
const pendientes = [
  "Editor de manuscritos con Tiptap",
  "Generador de novelas y agentes autónomos",
  "Evaluación literaria con la rúbrica v1",
];

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-16 sm:px-6">
      <header className="flex flex-col gap-3">
        <p className="text-sm uppercase tracking-widest text-[var(--color-muted)]">
          Fase 0 · Fundamentos
        </p>
        <h1 className="text-4xl font-semibold">Novel Engine</h1>
        <p className="text-lg text-[var(--color-muted)]">
          Entorno privado de escritura y edición literaria asistida por IA.
          Esta fase establece la estructura, la rúbrica y el benchmark inicial.
        </p>
      </header>

      <section aria-labelledby="pendientes-titulo" className="flex flex-col gap-3">
        <h2 id="pendientes-titulo" className="text-xl font-medium">
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
