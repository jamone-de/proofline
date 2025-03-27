(function () {
  var root = document.documentElement;
  function setTheme(mode) {
    root.setAttribute("data-theme", mode);
    try { localStorage.setItem("brightshop-theme", mode); } catch (e) {}
  }
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var dark = root.getAttribute("data-theme") === "dark" ||
        (root.getAttribute("data-theme") === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      setTheme(dark ? "light" : "dark");
    });
  }
  var menu = document.getElementById("menu-btn");
  if (menu) {
    menu.addEventListener("click", function () { document.body.classList.toggle("nav-open"); });
    document.addEventListener("click", function (event) {
      if (document.body.classList.contains("nav-open") && !event.target.closest(".rail") && !event.target.closest("#menu-btn")) {
        document.body.classList.remove("nav-open");
      }
    });
  }

  // calculator: add / remove cart rows
  var rows = document.getElementById("cart-rows");
  var add = document.getElementById("add-row");
  if (rows && add) {
    add.addEventListener("click", function () {
      var clone = rows.querySelector(".cart-row").cloneNode(true);
      clone.querySelector("select").selectedIndex = 0;
      clone.querySelector("input").value = 1;
      rows.appendChild(clone);
    });
    rows.addEventListener("click", function (event) {
      var button = event.target.closest("[data-remove]");
      if (button && rows.querySelectorAll(".cart-row").length > 1) {
        button.closest(".cart-row").remove();
      }
    });
  }

  // clickable table rows
  document.querySelectorAll("tr[data-href]").forEach(function (row) {
    row.addEventListener("click", function (event) {
      if (!event.target.closest("a")) { window.location = row.getAttribute("data-href"); }
    });
  });
})();
