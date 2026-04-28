(() => {
  const projectName = "Triad";
  const defaultName = "Chainlit";

  const renameTextNodes = (root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeValue && node.nodeValue.trim() === defaultName) {
        node.nodeValue = projectName;
      }
    }
  };

  const applyBranding = () => {
    renameTextNodes(document.body);
    document.title = projectName;
  };

  applyBranding();

  const observer = new MutationObserver(() => applyBranding());
  observer.observe(document.body, { childList: true, subtree: true });
})();
