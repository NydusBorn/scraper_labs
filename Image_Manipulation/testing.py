import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import cv2
    import skimage
    import skimage.restoration
    import numpy as np
    return cv2, mo, np, skimage


@app.cell
def _(cv2, mo):
    t_image = cv2.imread("./Image_Manipulation/test_image_2.png")
    t_image = cv2.cvtColor(t_image, cv2.COLOR_BGR2RGB)
    mo.image(t_image, rounded=True)
    return (t_image,)


@app.cell
def _(cv2, mo, t_image):
    gray_image = cv2.cvtColor(cv2.cvtColor(t_image, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    mo.image(gray_image, rounded=True)
    return (gray_image,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    Основное применение для изменения цветового пространства - применение тех или иных алгоритмов.

    Определенные алгоритмы работают только с определенными цветовыми пространствами, а в других случаях, выполнение той или иной задачи намного проще в другом цветовом пространстве, например изменение цвета без изменения яркости намного проще проводить в пространстве HSV, а не RGB.
    """
    )
    return


@app.cell
def _(cv2, gray_image, mo):
    _, thr = cv2.threshold(cv2.cvtColor(gray_image, cv2.COLOR_RGB2GRAY) , 128, 255, cv2.THRESH_TRIANGLE)
    mo.image(thr, rounded=True)
    return (thr,)


@app.cell
def _(cv2, mo, t_image, thr):
    def _():
        conts, h = cv2.findContours(thr,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        tem = t_image.copy() 
        return mo.image(cv2.drawContours(tem, conts, -1, (255,255,255), 2), rounded=True)
    _()
    return


@app.cell
def _(mo, np, skimage, t_image):
    noisy_img = skimage.util.random_noise(t_image/255.0, mode="gaussian", mean=0.05) * 255.0
    noisy_img = np.clip(noisy_img, 0, 255).astype(np.uint8)
    denoised_img = skimage.restoration.denoise_tv_bregman(noisy_img)
    mo.image_compare(noisy_img, denoised_img)
    return


@app.cell
def _(cv2, mo, t_image):
    def _():
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (5,5))
        eroded = cv2.morphologyEx(t_image, cv2.MORPH_ERODE, kernel)
        return eroded
    mo.image(_(), rounded=True)
    return


@app.cell
def _(cv2, mo, t_image):
    def _():
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        eroded = cv2.morphologyEx(t_image, cv2.MORPH_ERODE, kernel)
        return eroded
    mo.image(_(), rounded=True)
    return


@app.cell
def _(cv2, mo, t_image):
    def _():
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        eroded = cv2.morphologyEx(t_image, cv2.MORPH_DILATE, kernel)
        return eroded
    mo.image(_(), rounded=True)
    return


@app.cell
def _(cv2, mo, t_image):
    def _():
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        eroded = cv2.morphologyEx(t_image, cv2.MORPH_TOPHAT, kernel)
        return eroded
    mo.image(_(), rounded=True)
    return


@app.cell
def _(cv2, mo, t_image):
    scaled = cv2.resize(t_image, (128, 128), interpolation=cv2.INTER_AREA)
    mo.image(scaled, rounded=True)
    return


@app.cell
def _(cv2, mo, np, t_image):
    points1 = np.float32([[0,0], [1000,0], [0,350], [1000,500]])
    points2 = np.float32([[0,0], [1000,0], [0,500], [1000,500]])
    tf = cv2.getPerspectiveTransform(points1, points2)
    warped = cv2.warpPerspective(t_image, tf, (1000,500))
    mo.image(warped, rounded=True)
    return


if __name__ == "__main__":
    app.run()
