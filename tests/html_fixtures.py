"""HTML fixtures for the compliance-checker tests.

Two small variants per checker: one fully compliant, one with multiple
violations. Tests assert specific findings rather than overall verdicts where
possible, so fixture tweaks don't cascade across the suite.
"""

from __future__ import annotations

COMPLIANT_PROJECT_HTML = """
<html>
  <head><title>Apache Foo &mdash; the Foo software</title></head>
  <body>
    <header>
      <h1>Apache Foo&trade;</h1>
    </header>
    <nav>
      <a href="https://www.apache.org/licenses/">License</a>
      <a href="https://www.apache.org/foundation/sponsorship.html">Sponsorship</a>
      <a href="https://www.apache.org/foundation/thanks.html">Thanks</a>
      <a href="https://www.apache.org/security/">Security</a>
      <a href="https://privacy.apache.org/policies/privacy-policy-public.html">Privacy</a>
      <a href="https://www.apache.org/">Apache Software Foundation</a>
    </nav>
    <main>
      <p>Apache Foo software provides a thing that does the foo.</p>
      <img src="/img/foo-logo.png" alt="Apache Foo logo" />
    </main>
    <footer>
      <p>Apache Foo, Foo, Apache, the Apache feather logo, and the Apache Foo logo
         are trademarks or registered trademarks of The Apache Software Foundation.
         All other marks mentioned may be trademarks or registered trademarks
         of their respective owners.</p>
    </footer>
  </body>
</html>
"""


# Page that uses a project logo containing the ASF feather mark but does NOT
# include a TM/(R) anywhere in the page text. Used to verify the FAIL tier
# of logo_tm.
FEATHER_LOGO_NO_TM_HTML = """
<html>
  <head><title>Apache Foo</title></head>
  <body>
    <header><h1>Apache Foo</h1></header>
    <nav>
      <a href="https://www.apache.org/licenses/">License</a>
      <a href="https://www.apache.org/foundation/sponsorship.html">Sponsorship</a>
      <a href="https://www.apache.org/foundation/thanks.html">Thanks</a>
      <a href="https://www.apache.org/security/">Security</a>
      <a href="https://privacy.apache.org/policies/privacy-policy-public.html">Privacy</a>
      <a href="https://www.apache.org/">Apache</a>
    </nav>
    <main>
      <p>Apache Foo software provides things.</p>
      <img src="/img/foo-feather-logo.svg" alt="Apache Foo feather logo" />
    </main>
    <footer>
      <p>Apache Foo and Apache are trademarks of The Apache Software Foundation.</p>
    </footer>
  </body>
</html>
"""


NONCOMPLIANT_PROJECT_HTML = """
<html>
  <head><title>Foo &mdash; just Foo</title></head>
  <body>
    <header>
      <h1>Foo</h1>
    </header>
    <main>
      <p>Foo is a project. Use Foo for things.</p>
    </main>
    <footer>
      <p>Copyright 2026 Foo contributors.</p>
    </footer>
  </body>
</html>
"""


PODLING_COMPLIANT_HTML = """
<html>
  <head><title>Apache Foo (Incubating)</title></head>
  <body>
    <header><h1>Apache Foo&trade; (Incubating)</h1></header>
    <nav>
      <a href="https://www.apache.org/licenses/">License</a>
      <a href="https://www.apache.org/foundation/sponsorship.html">Sponsorship</a>
      <a href="https://www.apache.org/foundation/thanks.html">Thanks</a>
      <a href="https://www.apache.org/security/">Security</a>
      <a href="https://privacy.apache.org/policies/privacy-policy-public.html">Privacy</a>
      <a href="https://www.apache.org/">Apache</a>
    </nav>
    <main>
      <p>Apache Foo software provides streaming things.</p>
      <p>
        Apache Foo is an effort undergoing incubation at The Apache Software
        Foundation (ASF), sponsored by the Incubator. Incubation is required of
        all newly accepted projects until a further review indicates that the
        infrastructure, communications, and decision making process have
        stabilized in a manner consistent with other successful ASF projects.
      </p>
    </main>
    <footer>
      <p>Apache Foo, Foo, Apache, and the Apache feather logo are trademarks
      or registered trademarks of The Apache Software Foundation. All other
      marks are trademarks of their respective owners.</p>
    </footer>
  </body>
</html>
"""


# Third-party use cases

COMPLIANT_THIRD_PARTY_HTML = """
<html>
  <head><title>YoyoStream &mdash; Powered By Apache Foo</title></head>
  <body>
    <h1>YoyoStream</h1>
    <p>YoyoStream is Powered By Apache Foo and integrates with the Apache
    Foo project. YoyoStream is not affiliated with the Apache Software
    Foundation.</p>
    <p>Visit the upstream project at
       <a href="https://foo.apache.org/">foo.apache.org</a>.</p>
    <footer>
      <p>Apache, Apache Foo, and Foo are trademarks of The Apache Software Foundation.
      All other marks are trademarks of their respective owners.</p>
    </footer>
  </body>
</html>
"""


NONCOMPLIANT_THIRD_PARTY_HTML = """
<html>
  <head><title>Foo Pro &mdash; the official Foo</title></head>
  <body>
    <h1>Foo Pro</h1>
    <p>Foo Pro is the enterprise version of Foo. Built on Foo technology.</p>
    <img src="https://example.com/apache-feather.png" alt="Apache feather" />
  </body>
</html>
"""
