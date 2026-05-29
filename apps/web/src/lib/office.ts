export async function convertOfficeToPdf(file: File, convertUrl: string) {
  const formData = new FormData();
  formData.append("files", file);

  const response = await fetch(convertUrl, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Gotenberg conversion failed: ${response.status}`);
  }

  return response.blob();
}
