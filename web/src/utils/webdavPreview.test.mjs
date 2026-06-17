import assert from 'node:assert/strict'
import { isWebdavPreviewSupported } from './webdavPreview.mjs'

assert.equal(isWebdavPreviewSupported('manual.pdf'), true)
assert.equal(isWebdavPreviewSupported('INSTALL.DOCX'), true)
assert.equal(isWebdavPreviewSupported('report.xlsx?download=1'), true)
assert.equal(isWebdavPreviewSupported('archive.zip'), false)
assert.equal(isWebdavPreviewSupported('legacy.doc'), false)
assert.equal(isWebdavPreviewSupported('README'), false)
