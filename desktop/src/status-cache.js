class StatusCache {
  constructor(loader, ttl = 30_000, onUpdate = () => {}) {
    this.loader = loader;
    this.ttl = ttl;
    this.onUpdate = onUpdate;
    this.value = null;
    this.hasValue = false;
    this.loadedAt = 0;
    this.pending = null;
  }

  refresh() {
    if (this.pending) return this.pending;
    this.pending = (async () => {
      const value = await this.loader();
      this.value = value;
      this.hasValue = true;
      this.loadedAt = Date.now();
      this.onUpdate(value);
      return value;
    })().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }

  get() {
    if (!this.hasValue) return this.refresh();
    if (Date.now() - this.loadedAt >= this.ttl) {
      this.refresh().catch(() => {});
    }
    return Promise.resolve(this.value);
  }

  invalidate() {
    this.loadedAt = 0;
  }
}

module.exports = { StatusCache };
