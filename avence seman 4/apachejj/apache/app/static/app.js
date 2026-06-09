import PocketBase from 'https://cdn.jsdelivr.net/npm/pocketbase@0.21.5/+esm'

const pb = new PocketBase('http://127.0.0.1:8090')

async function cargarProductos() {

    const productos = await pb
        .collection('products')
        .getFullList()

    const contenedor =
        document.getElementById('productos')

    for (const p of productos) {

        const imageUrl =
            pb.files.getURL(p, p.image)

        contenedor.innerHTML += `
        
            <div class="card">

                <img
                    src="${imageUrl}"
                    width="200"
                >

                <h3>${p.name}</h3>

            </div>

        `
    }
}

cargarProductos()