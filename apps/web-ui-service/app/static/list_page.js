(function () {
  function mountSearchField(options) {
    const input = options && options.input;
    if (!input) return;
    const clearButton = options.clearButton || null;
    const searchButton = options.searchButton || null;
    const onSearch = typeof options.onSearch === 'function' ? options.onSearch : function () {};

    function syncClear() {
      if (!clearButton) return;
      clearButton.hidden = !String(input.value || '').trim();
    }

    input.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      onSearch();
    });
    input.addEventListener('input', syncClear);
    if (clearButton) {
      clearButton.addEventListener('click', function () {
        input.value = '';
        syncClear();
        onSearch();
        input.focus();
      });
    }
    if (searchButton) {
      searchButton.addEventListener('click', function () {
        onSearch();
      });
    }
    syncClear();
  }

  function bindSortHeaders(options) {
    const container = options && options.container;
    const keyInput = options && options.keyInput;
    const dirInput = options && options.dirInput;
    const onChange = typeof options?.onChange === 'function' ? options.onChange : function () {};
    if (!container || !keyInput || !dirInput) return;

    function sync() {
      const currentKey = String(keyInput.value || '').trim();
      const currentDir = String(dirInput.value || '').trim() || 'default';
      container.querySelectorAll('[data-sort-key]').forEach(function (button) {
        const sortKey = String(button.getAttribute('data-sort-key') || '').trim();
        const isActive = sortKey && sortKey === currentKey && currentDir !== 'default';
        const dir = isActive ? currentDir : 'default';
        button.dataset.sortDir = dir;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-sort', dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : 'none');
      });
    }

    container.querySelectorAll('[data-sort-key]').forEach(function (button) {
      button.addEventListener('click', function () {
        const nextKey = String(button.getAttribute('data-sort-key') || '').trim();
        const defaultDir = String(button.getAttribute('data-sort-default') || 'asc').trim() || 'asc';
        const currentKey = String(keyInput.value || '').trim();
        const currentDir = String(dirInput.value || '').trim() || 'default';
        if (currentKey !== nextKey) {
          keyInput.value = nextKey;
          dirInput.value = defaultDir;
        } else if (currentDir === defaultDir) {
          dirInput.value = defaultDir === 'asc' ? 'desc' : 'asc';
        } else if (currentDir === (defaultDir === 'asc' ? 'desc' : 'asc')) {
          keyInput.value = '';
          dirInput.value = 'default';
        } else {
          keyInput.value = nextKey;
          dirInput.value = defaultDir;
        }
        sync();
        onChange(keyInput.value, dirInput.value);
      });
    });

    sync();
    return { sync };
  }

  function sortItems(items, key, direction, definitions) {
    const rows = Array.isArray(items) ? items.slice() : [];
    const currentKey = String(key || '').trim();
    const currentDirection = String(direction || 'default').trim();
    if (!currentKey || currentDirection === 'default') return rows;
    const definition = definitions && definitions[currentKey];
    if (!definition) return rows;
    const getter = typeof definition === 'function' ? definition : definition.get;
    const type = typeof definition === 'function' ? 'string' : String(definition.type || 'string');
    const factor = currentDirection === 'desc' ? -1 : 1;
    return rows.sort(function (left, right) {
      const leftValue = getter(left);
      const rightValue = getter(right);
      if (type === 'number') return (Number(leftValue || 0) - Number(rightValue || 0)) * factor;
      if (type === 'date') return String(leftValue || '').localeCompare(String(rightValue || '')) * factor;
      return String(leftValue || '').localeCompare(String(rightValue || ''), 'zh-CN') * factor;
    });
  }

  function renderRowMenu(actions) {
    const items = Array.isArray(actions) ? actions.filter(Boolean) : [];
    if (!items.length) return '-';
    return '<details class="row-more-menu"><summary class="row-more-menu-trigger">更多</summary><div class="row-more-menu-panel">' + items.map(function (item) {
      const label = String(item.label || '').trim() || '查看';
      const extraClass = item.className ? ' ' + String(item.className).trim() : '';
      if (item.href) {
        const target = item.target ? ' target="' + String(item.target) + '"' : '';
        const rel = item.rel ? ' rel="' + String(item.rel) + '"' : '';
        return '<a class="row-more-menu-item' + extraClass + '" href="' + String(item.href) + '"' + target + rel + '>' + label + '</a>';
      }
      return '<button type="button" class="row-more-menu-item' + extraClass + '" data-row-action="' + String(item.action || '').trim() + '" data-row-id="' + String(item.id || '').trim() + '">' + label + '</button>';
    }).join('') + '</div></details>';
  }

  window.ListPage = {
    bindSortHeaders,
    mountSearchField,
    renderRowMenu,
    sortItems,
  };
})();
