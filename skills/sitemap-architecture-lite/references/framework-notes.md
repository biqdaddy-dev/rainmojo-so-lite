# Framework notes

Per-framework specifics for implementing the sitemap standard. Read only the
section for the stack in front of you.

**One thing has changed across all of them.** Browsers are removing client-side
XSLT (Chrome stops honouring it on 17 November 2026; Firefox and Safari intend
the same). Attaching the `<?xml-stylesheet?>` instruction is still correct and
still worth doing, because it is inert where unsupported and free where it
works, but it is no longer a reason to fight a framework. Where a section below
once said "hand-roll this to get the styled view", the remaining reason to
hand-roll is the `<sitemapindex>` root. The durable readable view is an HTML
sitemap page at its own URL; the main skill has the rules for it.

## Contents

- [Next.js App Router](#nextjs-app-router)
- [Django](#django)
- [Static hosting and CDNs](#static-hosting-and-cdns)
- [Multi-tenant and multi-site systems](#multi-tenant-and-multi-site-systems)

---

## Next.js App Router

Two constraints decide the approach, and both come from the built-in
`sitemap.ts` file convention:

1. **No automatic index.** `generateSitemaps()` produces per-id sub-sitemaps at
   `/.../sitemap/[id].xml`. Nothing in Next.js builds a combined index file
   with a `<sitemapindex>` root.
2. **No stylesheet hook, no root-tag control.** The convention always
   serializes the returned `MetadataRoute.Sitemap` array into a `<urlset>` of
   `<url>` entries. There is no supported option to emit an
   `<?xml-stylesheet?>` processing instruction or to change the root element.

`MetadataRoute.Sitemap` does support `alternates.languages`, so hreflang
alternates alone do not force you off the convention. **An index file does. The
missing stylesheet hook no longer does**, now that the styled view is a
progressive enhancement with an end date: if the only thing the convention
cannot give you is the processing instruction, stay on the convention and put
the readable view in an HTML sitemap page, which is a normal route anyway.

**The trade-off.** Getting a spec-correct `<sitemapindex>` root, and with it the
option of the styled browser view, means hand-rolling the XML in Route
Handlers:

```ts
return new Response(xml, {
  headers: { "Content-Type": "application/xml" },
});
```

That gives up `MetadataRoute.Sitemap`'s type safety and the convention's
built-in caching semantics, which you recover manually via route segment
config (`export const revalidate` / `dynamic`).

**Do not mix the two mechanisms in one tree.** If you hand-roll at all, use
`route.ts` for the index and every sub-sitemap and keep `generateSitemaps()`
out of the picture. Two XML generation paths in one app is how the namespace
declarations end up different between files.

### Layout

```
app/
  sitemap.xsl/route.ts          # stylesheet, Content-Type: text/xsl
  sitemap.xml/route.ts          # <sitemapindex>
  sitemaps/
    pages-th.xml/route.ts
    services-th.xml/route.ts
  sitemap/page.tsx              # the HTML sitemap page, for people
lib/
  sitemap-xml.ts                # buildUrlsetXml(), buildSitemapIndexXml()
```

A directory named `sitemap.xml` containing `route.ts` serves the literal path
`/sitemap.xml`, which is what keeps previously submitted URLs resolving.

### Caching

Route handlers default to dynamic once they read request data. If the sitemap
is derived from a data snapshot rather than the request, keep it static and
revalidate on a schedule or on a publish event:

```ts
export const revalidate = 3600;
```

Reading `headers()` or `searchParams` in a sitemap route forces it dynamic on
every crawl, which is worth avoiding — crawler traffic is exactly the traffic
this file exists to serve.

---

## Django

Django's `django.contrib.sitemaps` gives you an index for free via
`sitemap_index` / the `sitemaps` view, and it paginates. What it does not give
you is the `<?xml-stylesheet?>` instruction or `xhtml:link` alternates in the
default template.

Both are template-level fixes rather than architectural ones:

- **Stylesheet and alternates:** override `sitemap.xml` and `sitemap_index.xml`
  in your own `templates/` directory. Copy Django's originals, add the
  processing instruction as the second line, add the `xmlns:xhtml` declaration
  to `<urlset>`, and emit the alternate cluster per URL. The alternates are the
  part that matters; the processing instruction is a one-line enhancement you
  add while you are in the file, not a reason to override a template on its
  own.
- **Alternates data:** add a method on the `Sitemap` subclass that returns the
  cluster for an object, and call it from the overridden template.
- **`i18n = True`** on a `Sitemap` subclass generates one entry per language
  and can emit alternates via `alternates = True`, which covers many cases
  without a custom template. Check whether it produces reciprocal clusters for
  your URL scheme before writing anything custom.

Serve the stylesheet from a view with an explicit content type rather than
through `staticfiles`, for the MIME-type reason in the main skill. The HTML
sitemap page is an ordinary Django view over the same querysets the `Sitemap`
subclasses use; build it from those, not from a second set of filters.

---

## Static hosting and CDNs

- **MIME type was the usual failure.** Many static hosts serve `.xsl` as
  `text/plain` or `application/octet-stream`, and browsers then skip the
  transform silently. Configure the host explicitly (`_headers`,
  `netlify.toml`, `staticwebapp.config.json`, CloudFront response headers
  policy, whatever the platform uses) or serve the stylesheet from a function.
  **Time-box this.** The payoff ends when browsers stop running XSLT, so if a
  host fights you, ship the HTML sitemap page as a static page instead and
  leave the stylesheet unstyled. A static host is the one place where the
  server-side transform is not available anyway.
- **The readable view on a static host.** Generate the HTML sitemap page at
  build time from the same data that generates the XML, in the same build step.
  Two generators reading two sources is how the page and the sitemap come to
  disagree about what the site contains.
- **Compression.** XML sitemaps compress extremely well. Make sure gzip or
  brotli is on for `application/xml` and measure the compressed size of your own
  file, because that is the size that decides how urgent splitting really is.
- **Cache headers.** A sitemap that changes on publish wants a short
  `max-age` with revalidation, not a long immutable cache. A crawler holding a
  stale sitemap is slower to find new pages than one that refetches.

---

## Multi-tenant and multi-site systems

When one codebase serves many sites, the split axes are content type and
locale **within a single site** — not across sites. Each site gets its own
`/sitemap.xml` at its own origin.

Specific things that bite:

- **Origin resolution.** Build absolute URLs from the site's configured domain,
  never from the inbound `Host` header. A Host-derived URL is how one tenant's
  sitemap ends up advertising another tenant's hostname, and it passes every
  single-tenant test.
- **One public-visibility function.** If the platform has a notion of approved
  or published content, exactly one function should decide it, and every
  sub-sitemap should call it. Per-file queries drift, and the drift shows up as
  a draft URL in a sitemap.
- **Locale routes are per-site data, not a global constant.** A site declaring
  only one locale must not emit hreflang at all — a single-member alternate
  cluster is meaningless and some validators flag it.
- **Shared builder, per-site config.** The type list, locale list, and cap
  belong in per-site configuration passed to the same builder, so adding a site
  never means adding sitemap code.
