// Populate the sidebar
//
// This is a script, and not included directly in the page, to control the total size of the book.
// The TOC contains an entry for each page, so if each page includes a copy of the TOC,
// the total size of the page becomes O(n**2).
class MDBookSidebarScrollbox extends HTMLElement {
    constructor() {
        super();
    }
    connectedCallback() {
        this.innerHTML = '<ol class="chapter"><li class="chapter-item expanded affix "><a href="index.html">About This Reference</a></li><li class="chapter-item expanded "><a href="lexical-structure.html"><strong aria-hidden="true">1.</strong> Lexical Structure</a></li><li><ol class="section"><li class="chapter-item expanded "><a href="literals.html"><strong aria-hidden="true">1.1.</strong> Literals</a></li></ol></li><li class="chapter-item expanded "><a href="execution.html"><strong aria-hidden="true">2.</strong> Source Files and Execution</a></li><li class="chapter-item expanded "><a href="bindings-and-scope.html"><strong aria-hidden="true">3.</strong> Bindings, Initialization, and Scope</a></li><li class="chapter-item expanded "><a href="values.html"><strong aria-hidden="true">4.</strong> Values, Copies, and Places</a></li><li class="chapter-item expanded "><a href="types-and-conversions.html"><strong aria-hidden="true">5.</strong> Types and Conversions</a></li><li><ol class="section"><li class="chapter-item expanded "><a href="numeric-types.html"><strong aria-hidden="true">5.1.</strong> Numeric Types</a></li></ol></li><li class="chapter-item expanded "><a href="expressions-and-operators.html"><strong aria-hidden="true">6.</strong> Expressions and Evaluation</a></li><li class="chapter-item expanded "><a href="operators-and-precedence.html"><strong aria-hidden="true">7.</strong> Operators and Precedence</a></li><li class="chapter-item expanded "><a href="functions-and-calls.html"><strong aria-hidden="true">8.</strong> Functions and Calls</a></li><li class="chapter-item expanded "><a href="control-flow-and-iteration.html"><strong aria-hidden="true">9.</strong> Control Flow</a></li><li class="chapter-item expanded "><a href="ranges-and-iteration.html"><strong aria-hidden="true">10.</strong> Ranges and Iteration</a></li><li class="chapter-item expanded "><a href="strings.html"><strong aria-hidden="true">11.</strong> Strings and Graphemes</a></li><li class="chapter-item expanded "><a href="arrays-and-containers.html"><strong aria-hidden="true">12.</strong> Arrays and Containers</a></li><li class="chapter-item expanded "><a href="objects.html"><strong aria-hidden="true">13.</strong> Structural Objects</a></li><li class="chapter-item expanded "><a href="physical-quantities.html"><strong aria-hidden="true">14.</strong> Physical Quantities</a></li><li class="chapter-item expanded "><a href="modules-and-imports.html"><strong aria-hidden="true">15.</strong> Modules and Imports</a></li><li class="chapter-item expanded "><a href="interoperability.html"><strong aria-hidden="true">16.</strong> µDewy and Host Interoperability</a></li><li class="chapter-item expanded "><a href="design-status.html"><strong aria-hidden="true">17.</strong> Design Maturity and Open Questions</a></li><li class="chapter-item expanded "><a href="compatibility.html"><strong aria-hidden="true">18.</strong> Implementation Compatibility</a></li></ol>';
        // Set the current, active page, and reveal it if it's hidden
        let current_page = document.location.href.toString().split("#")[0].split("?")[0];
        if (current_page.endsWith("/")) {
            current_page += "index.html";
        }
        var links = Array.prototype.slice.call(this.querySelectorAll("a"));
        var l = links.length;
        for (var i = 0; i < l; ++i) {
            var link = links[i];
            var href = link.getAttribute("href");
            if (href && !href.startsWith("#") && !/^(?:[a-z+]+:)?\/\//.test(href)) {
                link.href = path_to_root + href;
            }
            // The "index" page is supposed to alias the first chapter in the book.
            if (link.href === current_page || (i === 0 && path_to_root === "" && current_page.endsWith("/index.html"))) {
                link.classList.add("active");
                var parent = link.parentElement;
                if (parent && parent.classList.contains("chapter-item")) {
                    parent.classList.add("expanded");
                }
                while (parent) {
                    if (parent.tagName === "LI" && parent.previousElementSibling) {
                        if (parent.previousElementSibling.classList.contains("chapter-item")) {
                            parent.previousElementSibling.classList.add("expanded");
                        }
                    }
                    parent = parent.parentElement;
                }
            }
        }
        // Track and set sidebar scroll position
        this.addEventListener('click', function(e) {
            if (e.target.tagName === 'A') {
                sessionStorage.setItem('sidebar-scroll', this.scrollTop);
            }
        }, { passive: true });
        var sidebarScrollTop = sessionStorage.getItem('sidebar-scroll');
        sessionStorage.removeItem('sidebar-scroll');
        if (sidebarScrollTop) {
            // preserve sidebar scroll position when navigating via links within sidebar
            this.scrollTop = sidebarScrollTop;
        } else {
            // scroll sidebar to current active section when navigating via "next/previous chapter" buttons
            var activeSection = document.querySelector('#sidebar .active');
            if (activeSection) {
                activeSection.scrollIntoView({ block: 'center' });
            }
        }
        // Toggle buttons
        var sidebarAnchorToggles = document.querySelectorAll('#sidebar a.toggle');
        function toggleSection(ev) {
            ev.currentTarget.parentElement.classList.toggle('expanded');
        }
        Array.from(sidebarAnchorToggles).forEach(function (el) {
            el.addEventListener('click', toggleSection);
        });
    }
}
window.customElements.define("mdbook-sidebar-scrollbox", MDBookSidebarScrollbox);
