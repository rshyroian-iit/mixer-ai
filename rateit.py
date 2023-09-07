import streamlit as st
import firebase_admin
import time
from firebase_admin import credentials, firestore, storage

cred = credentials.Certificate('digital-pagoda-391303-firebase-adminsdk-7aaf2-bf38bcd759.json')

if not firebase_admin._apps:
    default_app = firebase_admin.initialize_app(cred, {
        'storageBucket': 'digital-pagoda-391303.appspot.com'
    })
db = firestore.client()
bucket = storage.bucket()

def create_user(user):
    doc_ref = db.collection('users').document(user)
    if not doc_ref.get().exists:
        doc_ref.set({'name': user, 'viewed': []})
    st.session_state.viewed = doc_ref.get().to_dict()['viewed']

def get_content(emojis=[]):
    collection_ref = db.collection('images')
    docs = collection_ref.stream()
    files_png = []
    for doc in docs:
        doc_dict = doc.to_dict()
        if 'prompt_id' not in doc_dict:
            continue
        prompt_item = db.collection('prompts').document(doc_dict['prompt_id']).get().to_dict()
        emoji_item = db.collection('emojis').document(prompt_item['emoji_id']).get().to_dict()
        if set(emojis).issubset(emoji_item['emoji_combo']):
            files_png.append(doc_dict['image_path'])
    files_png = [file for file in files_png if file not in st.session_state.viewed]
    if len(files_png) == 0:
        st.write('You have rated all the images!')
        st.stop()
    file_to_show = files_png[0]
    blob = bucket.blob(file_to_show)
    name = blob.name
    blob.download_to_filename(name)
    uid = name[12:-4]
    doc_ref = db.collection('images').document(uid)
    doc = doc_ref.get()
    doc_dict = doc.to_dict()
    prompt_item = db.collection('prompts').document(doc_dict['prompt_id']).get().to_dict()
    emoji_item = db.collection('emojis').document(prompt_item['emoji_id']).get().to_dict()
    prompt = prompt_item['prompt']
    emojis = emoji_item['emoji_combo']
    likes = doc_dict['likes']
    dislikes = doc_dict['dislikes']
    return name, prompt, emojis, likes, dislikes

if 'emojis' not in st.session_state:
    st.session_state.emojis = []

if 'emoji_list' not in st.session_state:
    collection_ref = db.collection('images')
    docs = collection_ref.stream()
    emoji_list = []
    for doc in docs:
        doc_dict = doc.to_dict()
        if 'prompt_id' not in doc_dict:
            continue
        prompt_item = db.collection('prompts').document(doc_dict['prompt_id']).get().to_dict()
        emoji_item = db.collection('emojis').document(prompt_item['emoji_id']).get().to_dict()
        emoji_list.append(emoji_item['emoji_combo'])
    emoji_list = list(set(emoji_list))
    st.session_state.emoji_list = emoji_list

if 'username' not in st.session_state:
    # Ask the user to authenticate
    st.markdown("## Please sign in to continue")
    onboarding_user = st.text_input("Enter your username:")
    if onboarding_user:
        st.session_state.username = onboarding_user
        create_user(st.session_state.username)
        st.experimental_rerun()
else:
    # Ask the user to select one specific emoji
    dropdown = st.selectbox('Select an emoji', st.session_state.emoji_list)
    if dropdown:
        st.session_state.emojis = [emoji for emoji in dropdown]
        st.session_state.file = get_content(st.session_state.emojis)
    # Start the application
    if 'file' not in st.session_state:
        st.session_state.file = get_content(st.session_state.emojis)

    st.title('Rate this image')

    # Create two columns
    col1, col2, col3 = st.columns([2,1,3])

    # Show the image in column 1
    with col1:
        name, prompt, emojis, likes, dislikes = st.session_state.file
        st.image(name, width=300)

    # Show the prompt, emojis and ranking in column 2
    with col3:
        name, prompt, emojis, likes, dislikes = st.session_state.file
        #st.write('Likes: ', likes)
        #st.write('Dislikes: ', dislikes)
        st.write('Prompt: ', prompt)
        st.write('Emojis: ', "".join(emojis))

        # Place the buttons in separate lines in column 2
        with st.form("form"):
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                liked = st.form_submit_button('Like')
            with col2:
                loved = st.form_submit_button('Love')
            with col3:
                disliked = st.form_submit_button('Dislike')

            # Go to the next image after any button is pressed
            if liked or disliked or loved:
                # update the viewed field in the user document
                doc_ref = db.collection('users').document(st.session_state.username)
                doc_ref.update({
                    'viewed': firestore.ArrayUnion([name])
                })
                # update the viewed field in the session state
                st.session_state.viewed.append(name)
                # record the rating in the database
                doc_ref = db.collection('ratings').document()
                doc_ref.set({
                    'timestamp': time.time(),
                    'user': st.session_state.username,
                    'image': name,
                    'rating': 'liked' if liked else 'disliked' if disliked else 'loved'
                })
                #update the image document
                doc_ref = db.collection('images').document(name[12:-4])
                doc_ref.update({
                    'likes': firestore.Increment(1) if liked else firestore.Increment(0),
                    'dislikes': firestore.Increment(1) if disliked else firestore.Increment(0),
                    'loved': firestore.Increment(1) if loved else firestore.Increment(0)
                })
                # update the file_index and file
                st.session_state.file = get_content(st.session_state.emojis)
                st.experimental_rerun()
    
        st.write('Progress:')
        collection_ref = db.collection('images')
        docs = collection_ref.stream()
        st.progress(len(st.session_state.viewed)/len(list(docs)))
