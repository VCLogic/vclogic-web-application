import ReactMarkdown, { defaultUrlTransform, type Components, type Options } from "react-markdown";
import remarkGfm from "remark-gfm";

interface SafeMarkdownProps {
  children: string;
  className?: string;
  components?: Components;
  remarkPlugins?: NonNullable<Options["remarkPlugins"]>;
}

const baseComponents: Components = {
  a: ({ children, href, ...props }) => {
    if (!href) return <span>{children}</span>;
    const external = /^https?:\/\//i.test(href);
    return <a {...props} href={href} {...(external ? { target: "_blank", rel: "noreferrer noopener" } : {})}>{children}</a>;
  },
  table: ({ children, ...props }) => (
    <div className="markdown-table-scroll" role="region" aria-label="Scrollable table" tabIndex={0}>
      <table {...props}>{children}</table>
    </div>
  ),
};

export function SafeMarkdown({ children, className, components, remarkPlugins = [] }: SafeMarkdownProps) {
  return (
    <div className={["safe-markdown", className].filter(Boolean).join(" ")}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, ...remarkPlugins]}
        components={{ ...baseComponents, ...components }}
        urlTransform={defaultUrlTransform}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
