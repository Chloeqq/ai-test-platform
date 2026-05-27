/**
 * 分页组件 - Pagination Component
 * 
 * 功能：
 * 1. 页码显示
 * 2. 上一页/下一页
 * 3. 跳转指定页
 * 4. 每页数量选择
 * 5. 总记录数显示
 * 
 * 使用示例：
 * const pagination = new Pagination('#pagination', {
 *   page: 1,
 *   page_size: 20,
 *   total_items: 156,
 *   onChange: (page, page_size) => loadData(page, page_size)
 * });
 */

class Pagination {
  constructor(containerSelector, options = {}) {
    this.container = document.querySelector(containerSelector);
    if (!this.container) {
      console.error('Pagination container not found:', containerSelector);
      return;
    }

    // 配置
    this.options = {
      page: 1,              // 当前页码
      page_size: 20,        // 每页数量
      total_items: 0,       // 总记录数
      max_visible_pages: 7, // 最多显示的页码数
      page_size_options: [10, 20, 50, 100], // 每页数量选项
      show_total: true,     // 是否显示总数
      show_quick_jumper: true, // 是否显示快速跳转
      onChange: null,       // 变化回调
      ...options
    };

    // 计算属性
    this.total_pages = Math.ceil(this.options.total_items / this.options.page_size) || 1;
    this.options.total_pages = this.total_pages;
    
    // 渲染
    this.render();
  }

  // 更新分页状态
  update(options) {
    this.options = { ...this.options, ...options };
    this.total_pages = Math.ceil(this.options.total_items / this.options.page_size) || 1;
    this.options.total_pages = this.total_pages;
    
    // 确保当前页码有效
    if (this.options.page > this.total_pages) {
      this.options.page = this.total_pages;
    }
    if (this.options.page < 1) {
      this.options.page = 1;
    }
    
    this.render();
  }

  // 渲染分页
  render() {
    const html = `
      <div class="pagination">
        ${this.options.show_total ? this.renderTotal() : ''}
        ${this.renderPageSizeSelector()}
        ${this.renderPager()}
        ${this.options.show_quick_jumper ? this.renderQuickJumper() : ''}
      </div>
    `;
    
    this.container.innerHTML = html;
    this.bindEvents();
  }

  // 渲染总数
  renderTotal() {
    const { total_items, page, page_size, total_pages } = this.options;
    const start = (page - 1) * page_size + 1;
    const end = Math.min(page * page_size, total_items);
    
    return `
      <div class="pagination-total">
        共 <strong>${total_items}</strong> 条记录
        ${total_pages > 1 ? `（第 ${page}/${total_pages} 页，显示 ${start}-${end} 条）` : ''}
      </div>
    `;
  }

  // 渲染每页数量选择器
  renderPageSizeSelector() {
    const { page_size, page_size_options } = this.options;
    
    const options = page_size_options
      .map(size => `<option value="${size}" ${size === page_size ? 'selected' : ''}>${size}条/页</option>`)
      .join('');
    
    return `
      <div class="pagination-page-size">
        <select class="page-size-select">
          ${options}
        </select>
      </div>
    `;
  }

  // 渲染页码
  renderPager() {
    const { page, total_pages, max_visible_pages } = this.options;
    
    if (total_pages <= 1) return '';
    
    const pages = this.calculateVisiblePages(page, total_pages, max_visible_pages);
    
    return `
      <div class="pagination-pager">
        <button class="pagination-btn first" ${page === 1 ? 'disabled' : ''} title="首页">
          «
        </button>
        <button class="pagination-btn prev" ${page === 1 ? 'disabled' : ''} title="上一页">
          ‹
        </button>
        
        ${pages.map(p => {
          if (p === 'ellipsis') {
            return '<span class="pagination-ellipsis">...</span>';
          }
          return `
            <button 
              class="pagination-btn page ${p === page ? 'active' : ''}" 
              data-page="${p}"
              title="第${p}页"
            >
              ${p}
            </button>
          `;
        }).join('')}
        
        <button class="pagination-btn next" ${page === total_pages ? 'disabled' : ''} title="下一页">
          ›
        </button>
        <button class="pagination-btn last" ${page === total_pages ? 'disabled' : ''} title="末页">
          »
        </button>
      </div>
    `;
  }

  // 计算可见的页码
  calculateVisiblePages(current, total, maxVisible) {
    if (total <= maxVisible) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    
    const pages = [];
    const half = Math.floor(maxVisible / 2);
    let start = current - half;
    let end = current + half;
    
    // 调整起始页
    if (start < 1) {
      start = 1;
      end = Math.min(total, maxVisible);
    }
    
    // 调整结束页
    if (end > total) {
      end = total;
      start = Math.max(1, total - maxVisible + 1);
    }
    
    // 添加起始省略号
    if (start > 2) {
      pages.push(1, 'ellipsis');
    } else if (start === 2) {
      pages.push(1);
    }
    
    // 添加中间页码
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }
    
    // 添加结束省略号
    if (end < total - 1) {
      pages.push('ellipsis', total);
    } else if (end === total - 1) {
      pages.push(total);
    }
    
    return pages;
  }

  // 渲染快速跳转
  renderQuickJumper() {
    return `
      <div class="pagination-jumper">
        前往
        <input type="number" class="page-jumper-input" min="1" max="${this.options.total_pages}" value="${this.options.page}">
        页
        <button class="page-jumper-btn">确定</button>
      </div>
    `;
  }

  // 绑定事件
  bindEvents() {
    // 每页数量选择
    const pageSizeSelect = this.container.querySelector('.page-size-select');
    if (pageSizeSelect) {
      pageSizeSelect.addEventListener('change', (e) => {
        const newPageSize = parseInt(e.target.value);
        this.options.onChange?.(1, newPageSize); // 改变每页数量时回到第一页
      });
    }
    
    // 页码按钮
    this.container.querySelectorAll('.pagination-btn.page').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const page = parseInt(e.target.dataset.page);
        this.options.onChange?.(page, this.options.page_size);
      });
    });
    
    // 上一页/下一页/首页/末页
    this.container.querySelector('.pagination-btn.prev')?.addEventListener('click', () => {
      if (this.options.page > 1) {
        this.options.onChange?.(this.options.page - 1, this.options.page_size);
      }
    });
    
    this.container.querySelector('.pagination-btn.next')?.addEventListener('click', () => {
      if (this.options.page < this.options.total_pages) {
        this.options.onChange?.(this.options.page + 1, this.options.page_size);
      }
    });
    
    this.container.querySelector('.pagination-btn.first')?.addEventListener('click', () => {
      if (this.options.page > 1) {
        this.options.onChange?.(1, this.options.page_size);
      }
    });
    
    this.container.querySelector('.pagination-btn.last')?.addEventListener('click', () => {
      if (this.options.page < this.options.total_pages) {
        this.options.onChange?.(this.options.total_pages, this.options.page_size);
      }
    });
    
    // 快速跳转
    const jumperInput = this.container.querySelector('.page-jumper-input');
    const jumperBtn = this.container.querySelector('.page-jumper-btn');
    
    if (jumperInput && jumperBtn) {
      jumperBtn.addEventListener('click', () => {
        const page = parseInt(jumperInput.value);
        if (page >= 1 && page <= this.options.total_pages) {
          this.options.onChange?.(page, this.options.page_size);
        }
      });
      
      jumperInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          jumperBtn.click();
        }
      });
    }
  }
}

// 使用示例
window.Pagination = Pagination;
