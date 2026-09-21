document.addEventListener("DOMContentLoaded", () => {
  const menu = document.querySelector(".menu-toggle");
  menu?.addEventListener("click", () => {
    const open = document.querySelector(".main-nav").classList.toggle("open");
    menu.setAttribute("aria-expanded", String(open));
  });
  document
    .querySelectorAll(".dismiss-alert")
    .forEach((button) =>
      button.addEventListener("click", () => button.closest(".alert").remove()),
    );

  function toggleFields(element, visible) {
    if (!element) return;
    element.hidden = !visible;
    element.querySelectorAll("input, select, textarea").forEach((input) => {
      if (input.required) input.dataset.required = "true";
      input.disabled = !visible;
      input.required = visible && input.dataset.required === "true";
    });
  }
  const roles = document.querySelectorAll('input[name="role"]');
  function updateRole() {
    const role =
      document.querySelector('input[name="role"]:checked')?.value || "donor";
    toggleFields(
      document.querySelector("[data-organization-fields]"),
      role !== "admin",
    );
    toggleFields(
      document.querySelector("[data-charity-fields]"),
      role === "charity",
    );
    toggleFields(
      document.querySelector("[data-admin-fields]"),
      role === "admin",
    );
  }
  if (roles.length) {
    roles.forEach((role) => role.addEventListener("change", updateRole));
    updateRole();
  } else
    document
      .querySelectorAll("[data-charity-fields]")
      .forEach((section) => toggleFields(section, !section.hidden));

  const confirm = document.querySelector("#confirm_password");
  const password = document.querySelector("#password");
  function passwordsMatch() {
    if (confirm)
      confirm.setCustomValidity(
        confirm.value && confirm.value !== password.value
          ? "Your passwords must match."
          : "",
      );
  }
  confirm?.addEventListener("input", passwordsMatch);
  password?.addEventListener("input", passwordsMatch);
  document.querySelectorAll("[data-demo]").forEach((button) =>
    button.addEventListener("click", () => {
      document.querySelector("#email").value =
        `${button.dataset.demo}@foodconnect.demo`;
      document.querySelector("#password").value = "Demo@12345";
      document.querySelector("#email").focus();
    }),
  );

  const now = new Date().toISOString().slice(0, 16);
  document.querySelectorAll('[data-date="past"]').forEach((input) => {
    input.max = now;
    if (!input.value) input.value = now;
  });
  document
    .querySelectorAll('[data-date="future"]')
    .forEach((input) => (input.min = now));

  document.querySelectorAll("[data-geolocate]").forEach((button) =>
    button.addEventListener("click", () => {
      const message = button.parentElement.querySelector(".geo-message");
      if (!navigator.geolocation) {
        message.textContent =
          "Location is not supported. Enter coordinates manually.";
        return;
      }
      button.disabled = true;
      message.textContent = "Finding your location…";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          document.querySelector('[name="latitude"]').value =
            position.coords.latitude.toFixed(6);
          document.querySelector('[name="longitude"]').value =
            position.coords.longitude.toFixed(6);
          message.textContent =
            "Coordinates updated. Please confirm your written address.";
          button.disabled = false;
        },
        () => {
          message.textContent =
            "Location could not be accessed. Enter coordinates manually.";
          button.disabled = false;
        },
        { timeout: 10000, maximumAge: 300000 },
      );
    }),
  );

  document.querySelectorAll("form").forEach((form) =>
    form.addEventListener("submit", (event) => {
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      const button = event.submitter;
      if (button && form.method.toLowerCase() === "post") {
        button.classList.add("loading");
        // Do not disable until after the browser serializes a named submit button.
        window.setTimeout(() => {
          button.disabled = true;
        }, 0);
      }
    }),
  );
  window.addEventListener("pageshow", () =>
    document.querySelectorAll("button.loading").forEach((button) => {
      button.disabled = false;
      button.classList.remove("loading");
    }),
  );

  const chart = document.querySelector("#status-chart");
  if (chart) {
    const data = JSON.parse(chart.dataset.chart);
    const max = Math.max(...Object.values(data), 1);
    const order = [
      "Available",
      "Matched",
      "Accepted",
      "Collected",
      "Delivered",
    ];
    order.forEach((label) => {
      const value = data[label] || 0;
      const column = document.createElement("div");
      column.className = "chart-item";
      const count = document.createElement("strong");
      count.textContent = value;
      const bar = document.createElement("div");
      bar.className = "chart-bar";
      bar.style.height = `${(value / max) * 115}px`;
      const caption = document.createElement("small");
      caption.textContent = label;
      column.append(count, bar, caption);
      chart.append(column);
    });
  }
});
