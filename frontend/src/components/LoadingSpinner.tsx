// Pokéball-themed spinner used during the /match request. Pure CSS, no SVG
// dependencies — keeps the loading state lightweight.
export function LoadingSpinner({ message = "Consulting the Pokédex..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-6 py-12">
      {/* Pokéball — top half red, bottom half white, with a center band + button */}
      <div className="relative h-20 w-20 animate-spin-slow">
        <div className="absolute inset-0 rounded-full border-4 border-slate-800 bg-white" />
        <div className="absolute inset-0 overflow-hidden rounded-full border-4 border-slate-800">
          <div className="h-1/2 w-full bg-red-500" />
        </div>
        <div className="absolute left-0 right-0 top-1/2 h-1.5 -translate-y-1/2 bg-slate-800" />
        <div className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-slate-800 bg-white" />
      </div>
      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">{message}</p>
    </div>
  );
}
