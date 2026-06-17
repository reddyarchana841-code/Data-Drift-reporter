// upload.js

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const alertBox = document.getElementById("upload-alert");
  alertBox.classList.add("d-none");

  const fileInput = document.getElementById("file");
  const datasetName = document.getElementById("dataset_name").value;

  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("dataset_name", datasetName);

  const submitBtn = e.target.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (res.ok) {
      alertBox.className = "alert alert-success";
      alertBox.textContent = "Dataset uploaded and first snapshot generated successfully!";
      alertBox.classList.remove("d-none");
      e.target.reset();

      setTimeout(() => {
        window.location.href = `/dataset/${data.dataset.id}`;
      }, 900);
    } else {
      alertBox.className = "alert alert-danger";
      alertBox.textContent = data.error || "Upload failed.";
      alertBox.classList.remove("d-none");
    }
  } catch (err) {
    alertBox.className = "alert alert-danger";
    alertBox.textContent = "Upload failed: " + err.message;
    alertBox.classList.remove("d-none");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Upload &amp; Generate Snapshot';
  }
});
