const image = document.querySelector('#image');
const feedback = document.querySelector('#image-feedback');
if (image && feedback) {
  image.addEventListener('change', () => {
    const file = image.files[0];
    feedback.textContent = file
      ? (file.size > 5 * 1024 * 1024 ? '画像は5 MiB以下にしてください。' : `選択中：${file.name}`)
      : '';
  });
}
