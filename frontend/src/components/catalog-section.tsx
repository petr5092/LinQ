import { useContext, type ReactNode } from "react"
import { CatalogSearchContext } from "@/lib/catalog-search"
import { cn } from "@/lib/utils"

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string
  eyebrow: string
  title: string
  children: ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-24 border-b border-border py-12 first:pt-8">
      <div className="mb-7 flex items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {eyebrow}
          </p>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        </div>
        <a
          href="#top"
          className="hidden text-xs text-muted-foreground hover:text-foreground sm:block"
        >
          Back to top ↑
        </a>
      </div>
      {children}
    </section>
  )
}

function Specimen({
  title,
  note,
  children,
  className,
  searchable = false,
}: {
  title: string
  note?: string
  children: ReactNode
  className?: string
  searchable?: boolean
}) {
  const query = useContext(CatalogSearchContext).trim().toLowerCase()
  if (searchable && query && !`${title} ${note ?? ""}`.toLowerCase().includes(query)) return null
  return (
    <div
      data-slot="specimen"
      className={cn("min-w-0 rounded-xl border border-border bg-card p-5", className)}
    >
      <div className="mb-5">
        <h3 className="text-sm font-medium">{title}</h3>
        {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
      </div>
      {children}
    </div>
  )
}

export { Section, Specimen }
