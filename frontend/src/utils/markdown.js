import { marked } from "marked";
import Prism from "prismjs";
import "prismjs/components/prism-javascript.js";
import "prismjs/components/prism-cpp.js";
import "prismjs/components/prism-python.js";

marked.setOptions({
  highlight: function(code, lang) {
    if (Prism.languages[lang]) {
      return Prism.highlight(code, Prism.languages[lang], lang);
    }
    return code;
  }
});

export function renderMarkdown(md) {
  return marked.parse(md || "");
}
